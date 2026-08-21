"""Phase 2: RS(48,32) round trip over the finalized native-DCT channel."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from pathlib import Path

import numpy as np
from reedsolo import RSCodec, ReedSolomonError

from phase1_native_dct_experiment import (
    QUALITIES,
    embed_native_dct,
    extract_native_dct,
    find_covers,
    recompress_with_pillow,
)


PAYLOAD_BYTES = 32
PARITY_BYTES = 16
CODEWORD_BYTES = PAYLOAD_BYTES + PARITY_BYTES  # RS(48,32)
PAIR_INDICES = (0, 2)


def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder="big")


def bits_to_bytes(bits: np.ndarray) -> bytes:
    if len(bits) % 8:
        raise ValueError("bit count must be byte-aligned")
    return np.packbits(bits, bitorder="big").tobytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--covers-dir", required=True)
    parser.add_argument("--output-dir", default="phase2_rs_results")
    parser.add_argument("--covers", type=int, default=15)
    parser.add_argument("--gap", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260821)
    args = parser.parse_args()

    out_dir = Path(args.output_dir).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    covers_dir = Path(args.covers_dir).resolve()
    covers = find_covers(covers_dir, args.covers)

    payload = np.random.default_rng(args.seed).bytes(PAYLOAD_BYTES)
    codec = RSCodec(PARITY_BYTES)
    codeword = bytes(codec.encode(payload))
    if len(codeword) != CODEWORD_BYTES:
        raise RuntimeError(f"expected RS(48,32) codeword, got {len(codeword)} bytes")
    bits = bytes_to_bits(codeword)
    (out_dir / "payload_sha256.txt").write_text(hashlib.sha256(payload).hexdigest() + "\n", encoding="utf-8")

    rows: list[dict[str, object]] = []
    for cover_number, cover in enumerate(covers, start=1):
        cover_id = cover.relative_to(covers_dir).as_posix()
        stego = out_dir / f"{cover_number:02d}_{cover.stem}_rs_stego.jpg"
        embed_native_dct(cover, stego, bits, args.gap, PAIR_INDICES)
        direct = bits_to_bytes(extract_native_dct(stego, len(bits), PAIR_INDICES))
        if direct != codeword:
            raise RuntimeError(f"native DCT round trip failed for {cover_id}")

        for quality in QUALITIES:
            recompressed = out_dir / f"{cover_number:02d}_{cover.stem}_rs_q{quality}.jpg"
            recompress_with_pillow(stego, recompressed, quality)
            extracted_bits = extract_native_dct(recompressed, len(bits), PAIR_INDICES)
            raw_bit_errors = int(np.count_nonzero(extracted_bits != bits))
            extracted_codeword = bits_to_bytes(extracted_bits)
            success = False
            corrected_symbols: int | None = None
            error = ""
            try:
                decoded, _, errata_positions = codec.decode(extracted_codeword)
                corrected_symbols = len(errata_positions)
                success = bytes(decoded) == payload
                if not success:
                    error = "decoded payload differed"
            except ReedSolomonError as exc:
                error = str(exc)

            rows.append({
                "cover": cover_id,
                "quality": quality,
                "payload_bytes": PAYLOAD_BYTES,
                "codeword_bytes": CODEWORD_BYTES,
                "raw_bit_errors": raw_bit_errors,
                "raw_ber": f"{raw_bit_errors / len(bits):.8f}",
                "rs_corrected_symbols": "" if corrected_symbols is None else corrected_symbols,
                "success": success,
                "error": error,
            })
            print(f"{cover_id:48.48s} q={quality:2d} raw={raw_bit_errors:3d}/{len(bits)} "
                  f"corrected={corrected_symbols!s:>2} success={success}")

    with (out_dir / "phase2_rs_trials.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("\nFull-message recovery by quality")
    for quality in QUALITIES:
        group = [row for row in rows if row["quality"] == quality]
        print(f"Q{quality}: {sum(bool(row['success']) for row in group)}/{len(group)}")


if __name__ == "__main__":
    main()
