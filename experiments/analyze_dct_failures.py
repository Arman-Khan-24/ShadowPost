"""Read-only analysis of existing Phase 1 JPEG trial artifacts.

This does not embed, alter, recompress, or otherwise generate any image. It
only re-extracts the native JPEG DCT bit ordering from already-produced files
and records failed bit positions and their payload block coordinates.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from experiments.common import (
    QUALITIES,
    find_covers,
    random_bits,
    parse_pair_indices,
)
from shadowpost.dct_codec import (
    extract_native_dct,
    luminance_coefficients,
    usable_pairs,
)
import jpeglib


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results/phase1")
    parser.add_argument(
        "--covers-dir", type=Path, help="override the archived Windows cover path"
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("results/local/phase1_failure_positions.csv"),
    )
    args = parser.parse_args()
    results_dir = Path(args.results_dir).resolve()
    config = json.loads((results_dir / "config.json").read_text(encoding="utf-8"))
    source_dir = args.covers_dir or Path(config["covers_dir"])
    pair_indices = parse_pair_indices(config.get("pair_indices", "0,1,2,3"))
    covers = find_covers(source_dir, int(config["covers"]))
    bit_count = int(config["bits"])
    payload = random_bits(bit_count, int(config["seed"]))

    rows: list[dict[str, object]] = []
    for cover_index, cover in enumerate(covers, start=1):
        stego = results_dir / f"{cover_index:02d}_{cover.stem}_stego.jpg"
        coeffs = luminance_coefficients(jpeglib.read_dct(str(stego)))
        slots = usable_pairs(coeffs, bit_count, pair_indices)
        total_blocks = len({(row, col) for row, col, _ in slots})
        cover_id = cover.relative_to(source_dir).as_posix()
        for quality in QUALITIES:
            recompressed = (
                results_dir / f"{cover_index:02d}_{cover.stem}_q{quality}.jpg"
            )
            extracted = extract_native_dct(recompressed, bit_count, pair_indices)
            failed = np.flatnonzero(payload != extracted).astype(int).tolist()
            failed_locations = [slots[index] for index in failed]
            failed_blocks = sorted({(row, col) for row, col, _ in failed_locations})
            rows.append(
                {
                    "cover": cover_id,
                    "quality": quality,
                    "bit_errors": len(failed),
                    "failed_bit_positions": ";".join(map(str, failed)),
                    "failed_bit_block_pair": ";".join(
                        f"{index}:(r{row},c{col},pair{pair})"
                        for index, (row, col, pair) in zip(
                            failed, failed_locations, strict=True
                        )
                    ),
                    "blocks_with_error": len(failed_blocks),
                    "total_payload_blocks": total_blocks,
                    "error_block_coordinates": ";".join(
                        f"(r{row},c{col})" for row, col in failed_blocks
                    ),
                }
            )

    out = args.output_file
    if out.exists():
        raise FileExistsError(f"refusing to overwrite existing analysis: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        if row["bit_errors"]:
            print(
                f"{row['cover']} q={row['quality']}: {row['bit_errors']} errors in "
                f"{row['blocks_with_error']}/{row['total_payload_blocks']} payload blocks"
            )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
