"""Phase 3: AES-256-GCM + RS(48,32) over the finalized native-DCT channel."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
from pathlib import Path

import numpy as np
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from reedsolo import RSCodec, ReedSolomonError

from phase1_native_dct_experiment import (
    QUALITIES,
    embed_native_dct,
    extract_native_dct,
    find_covers,
    recompress_with_pillow,
)
from phase2_rs_roundtrip import bits_to_bytes, bytes_to_bits


RS_DATA_BYTES = 32
RS_PARITY_BYTES = 16
RS_CODEWORD_BYTES = RS_DATA_BYTES + RS_PARITY_BYTES
NONCE_BYTES = 12
TAG_BYTES = 16
MAX_PLAINTEXT_BYTES = RS_DATA_BYTES - NONCE_BYTES - TAG_BYTES
PAIR_INDICES = (0, 2)
# The specified compact container has no room for a per-message salt. This
# versioned protocol salt is public and fixed; deployment code must treat the
# passphrase as secret and can supply an installation-specific salt later.
SCRYPT_SALT = b"ShadowPost/v1 AES-256-GCM scrypt salt"


def derive_aes256_key(passphrase: str) -> bytes:
    """Derive a 32-byte AES-256 key; the passphrase is never used directly."""
    return Scrypt(salt=SCRYPT_SALT, length=32, n=2**14, r=8, p=1).derive(passphrase.encode("utf-8"))


def encrypt_container(key: bytes, plaintext: bytes) -> bytes:
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise ValueError(f"plaintext is {len(plaintext)} bytes; maximum is {MAX_PLAINTEXT_BYTES}")
    nonce = os.urandom(NONCE_BYTES)
    ciphertext_and_tag = AESGCM(key).encrypt(nonce, plaintext, None)
    container = nonce + ciphertext_and_tag
    if len(container) != RS_DATA_BYTES:
        raise RuntimeError("unexpected AES-GCM container length")
    return container


def decrypt_container(key: bytes, container: bytes) -> bytes:
    if len(container) < NONCE_BYTES + TAG_BYTES:
        raise ValueError("AES-GCM container is truncated")
    return AESGCM(key).decrypt(container[:NONCE_BYTES], container[NONCE_BYTES:], None)


def negative_tests(key: bytes, payload: bytes, codec: RSCodec) -> tuple[bool, bool]:
    """Return (rs_rejected_over_capacity_damage, gcm_rejected_tampered_container)."""
    container = encrypt_container(key, payload)
    codeword = bytearray(codec.encode(container))
    for index in range(10):  # RS(48,32) corrects at most eight erroneous symbols.
        codeword[index] ^= 0x01
    try:
        codec.decode(bytes(codeword))
        rs_rejected = False
    except ReedSolomonError:
        rs_rejected = True

    tampered = bytearray(container)
    tampered[-1] ^= 0x01  # Change the GCM tag without changing ciphertext length.
    try:
        decrypt_container(key, bytes(tampered))
        gcm_rejected = False
    except InvalidTag:
        gcm_rejected = True
    return rs_rejected, gcm_rejected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--covers-dir", required=True)
    parser.add_argument("--output-dir", default="phase3_aes_gcm_results")
    parser.add_argument("--covers", type=int, default=15)
    parser.add_argument("--gap", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--passphrase", default="ShadowPost Phase 3 integration test passphrase")
    args = parser.parse_args()

    out_dir = Path(args.output_dir).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    covers_dir = Path(args.covers_dir).resolve()
    covers = find_covers(covers_dir, args.covers)
    plaintext = np.random.default_rng(args.seed).bytes(MAX_PLAINTEXT_BYTES)
    key = derive_aes256_key(args.passphrase)
    codec = RSCodec(RS_PARITY_BYTES)

    rows: list[dict[str, object]] = []
    for cover_number, cover in enumerate(covers, start=1):
        cover_id = cover.relative_to(covers_dir).as_posix()
        for quality in QUALITIES:
            container = encrypt_container(key, plaintext)  # New 12-byte nonce every trial.
            codeword = bytes(codec.encode(container))
            if len(codeword) != RS_CODEWORD_BYTES:
                raise RuntimeError("expected RS(48,32) codeword")
            bits = bytes_to_bits(codeword)
            stego = out_dir / f"{cover_number:02d}_{cover.stem}_q{quality}_stego.jpg"
            recompressed = out_dir / f"{cover_number:02d}_{cover.stem}_q{quality}.jpg"
            embed_native_dct(cover, stego, bits, args.gap, PAIR_INDICES)
            if bits_to_bytes(extract_native_dct(stego, len(bits), PAIR_INDICES)) != codeword:
                raise RuntimeError(f"native DCT round trip failed for {cover_id} q={quality}")
            recompress_with_pillow(stego, recompressed, quality)
            extracted_bits = extract_native_dct(recompressed, len(bits), PAIR_INDICES)
            raw_bit_errors = int(np.count_nonzero(extracted_bits != bits))
            success, corrected_symbols, error = False, "", ""
            try:
                recovered_container, _, errata = codec.decode(bits_to_bytes(extracted_bits))
                corrected_symbols = str(len(errata))
                success = decrypt_container(key, bytes(recovered_container)) == plaintext
                if not success:
                    error = "decrypted plaintext differed"
            except (ReedSolomonError, InvalidTag, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
            rows.append({
                "cover": cover_id,
                "quality": quality,
                "plaintext_bytes": len(plaintext),
                "container_bytes": len(container),
                "codeword_bytes": len(codeword),
                "raw_bit_errors": raw_bit_errors,
                "raw_ber": f"{raw_bit_errors / len(bits):.8f}",
                "rs_corrected_symbols": corrected_symbols,
                "success": success,
                "error": error,
            })
            print(f"{cover_id:48.48s} q={quality:2d} raw={raw_bit_errors:3d}/{len(bits)} "
                  f"corrected={corrected_symbols:>2} success={success}")

    with (out_dir / "phase3_trials.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    rs_rejected, gcm_rejected = negative_tests(key, plaintext, codec)
    (out_dir / "negative_test.txt").write_text(
        f"rs_over_capacity_rejected={rs_rejected}\ngcm_tampered_tag_rejected={gcm_rejected}\n", encoding="utf-8"
    )
    print(f"\nnegative: rs_over_capacity_rejected={rs_rejected}; gcm_tampered_tag_rejected={gcm_rejected}")
    print("Full-message recovery by quality")
    for quality in QUALITIES:
        group = [row for row in rows if row["quality"] == quality]
        print(f"Q{quality}: {sum(bool(row['success']) for row in group)}/{len(group)}")


if __name__ == "__main__":
    main()
