"""Phase 3: AES-256-GCM + RS(48,32) over the finalized native-DCT channel."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from cryptography.exceptions import InvalidTag
from reedsolo import RSCodec, ReedSolomonError

from shadowpost.dct_codec import embed_native_dct, extract_native_dct
from shadowpost.ecc import (
    RS_DATA_BYTES,
    RS_PARITY_BYTES,
    RS_CODEWORD_BYTES,
    bits_to_bytes,
    bytes_to_bits,
)
from shadowpost.crypto import (
    NONCE_BYTES,
    TAG_BYTES,
    derive_aes256_key,
    encrypt_message,
    decrypt_container,
)
from experiments.common import QUALITIES, find_covers, recompress_with_pillow

MAX_PLAINTEXT_BYTES = RS_DATA_BYTES - NONCE_BYTES - TAG_BYTES
PAIR_INDICES = (0, 2)


def encrypt_container(key: bytes, plaintext: bytes) -> bytes:
    """Preserve the phase-3 experiment's fixed 32-byte container."""
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise ValueError(
            f"plaintext is {len(plaintext)} bytes; maximum is {MAX_PLAINTEXT_BYTES}"
        )
    container = encrypt_message(key, plaintext)
    if len(container) != RS_DATA_BYTES:
        raise RuntimeError("unexpected AES-GCM container length")
    return container


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
    parser.add_argument("--output-dir", default="results/local/phase3_aes_gcm")
    parser.add_argument("--covers", type=int, default=15)
    parser.add_argument("--gap", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument(
        "--passphrase", default="ShadowPost Phase 3 integration test passphrase"
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir).resolve()
    if out_dir.exists():
        raise FileExistsError(
            f"refusing to overwrite existing experiment results: {out_dir}"
        )
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
            container = encrypt_container(
                key, plaintext
            )  # New 12-byte nonce every trial.
            codeword = bytes(codec.encode(container))
            if len(codeword) != RS_CODEWORD_BYTES:
                raise RuntimeError("expected RS(48,32) codeword")
            bits = bytes_to_bits(codeword)
            stego = out_dir / f"{cover_number:02d}_{cover.stem}_q{quality}_stego.jpg"
            recompressed = out_dir / f"{cover_number:02d}_{cover.stem}_q{quality}.jpg"
            embed_native_dct(cover, stego, bits, args.gap, PAIR_INDICES)
            if (
                bits_to_bytes(extract_native_dct(stego, len(bits), PAIR_INDICES))
                != codeword
            ):
                raise RuntimeError(
                    f"native DCT round trip failed for {cover_id} q={quality}"
                )
            recompress_with_pillow(stego, recompressed, quality)
            extracted_bits = extract_native_dct(recompressed, len(bits), PAIR_INDICES)
            raw_bit_errors = int(np.count_nonzero(extracted_bits != bits))
            success, corrected_symbols, error = False, "", ""
            try:
                recovered_container, _, errata = codec.decode(
                    bits_to_bytes(extracted_bits)
                )
                corrected_symbols = str(len(errata))
                success = (
                    decrypt_container(key, bytes(recovered_container)) == plaintext
                )
                if not success:
                    error = "decrypted plaintext differed"
            except (ReedSolomonError, InvalidTag, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
            rows.append(
                {
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
                }
            )
            print(
                f"{cover_id:48.48s} q={quality:2d} raw={raw_bit_errors:3d}/{len(bits)} "
                f"corrected={corrected_symbols:>2} success={success}"
            )

    with (out_dir / "phase3_trials.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    rs_rejected, gcm_rejected = negative_tests(key, plaintext, codec)
    (out_dir / "negative_test.txt").write_text(
        f"rs_over_capacity_rejected={rs_rejected}\ngcm_tampered_tag_rejected={gcm_rejected}\n",
        encoding="utf-8",
    )
    print(
        f"\nnegative: rs_over_capacity_rejected={rs_rejected}; gcm_tampered_tag_rejected={gcm_rejected}"
    )
    print("Full-message recovery by quality")
    for quality in QUALITIES:
        group = [row for row in rows if row["quality"] == quality]
        print(f"Q{quality}: {sum(bool(row['success']) for row in group)}/{len(group)}")


if __name__ == "__main__":
    main()
