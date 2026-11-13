"""Phase 1: native-JPEG DCT relative-pair robustness experiment.

This file deliberately uses jpeglib.read_dct() and DCTJPEG.write_dct().
Pillow is used only to simulate a downstream JPEG re-save; it never performs
embedding or extraction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


from shadowpost.dct_codec import embed_native_dct, extract_native_dct
from experiments.common import (
    QUALITIES,
    random_bits,
    parse_pair_indices,
    find_covers,
    recompress_with_pillow,
)


@dataclass(frozen=True)
class Trial:
    cover: str
    quality: int
    embedded_bits: int
    bit_errors: int

    @property
    def ber(self) -> float:
        return self.bit_errors / self.embedded_bits


def run(args: argparse.Namespace) -> list[Trial]:
    source_dir = Path(args.covers_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    if out_dir.exists():
        raise FileExistsError(
            f"refusing to overwrite existing experiment results: {out_dir}"
        )
    out_dir.mkdir(parents=True)

    pair_indices = parse_pair_indices(args.pair_indices)
    covers = find_covers(source_dir, args.covers)
    payload = random_bits(args.bits, args.seed)
    (out_dir / "payload_sha256.txt").write_text(
        hashlib.sha256(payload.tobytes()).hexdigest() + "\n", encoding="utf-8"
    )
    (out_dir / "config.json").write_text(
        json.dumps(vars(args), indent=2) + "\n", encoding="utf-8"
    )

    trials: list[Trial] = []
    for cover_index, cover in enumerate(covers, start=1):
        stego = out_dir / f"{cover_index:02d}_{cover.stem}_stego.jpg"
        embed_native_dct(cover, stego, payload, args.gap, pair_indices)
        # Validate the lossless DCT write before introducing recompression.
        direct = extract_native_dct(stego, len(payload), pair_indices)
        if not np.array_equal(payload, direct):
            raise RuntimeError(f"native DCT round trip failed for {cover.name}")
        for quality in QUALITIES:
            recompressed = out_dir / f"{cover_index:02d}_{cover.stem}_q{quality}.jpg"
            recompress_with_pillow(stego, recompressed, quality)
            extracted = extract_native_dct(recompressed, len(payload), pair_indices)
            errors = int(np.count_nonzero(payload != extracted))
            cover_id = cover.relative_to(source_dir).as_posix()
            trials.append(Trial(cover_id, quality, len(payload), errors))
            print(
                f"{cover_id:48.48s} q={quality:2d} errors={errors:4d}/{len(payload)} BER={errors / len(payload):.6f}"
            )

    with (out_dir / "phase1_trials.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("cover", "quality", "embedded_bits", "bit_errors", "ber"),
        )
        writer.writeheader()
        writer.writerows(
            {
                "cover": t.cover,
                "quality": t.quality,
                "embedded_bits": t.embedded_bits,
                "bit_errors": t.bit_errors,
                "ber": f"{t.ber:.8f}",
            }
            for t in trials
        )
    return trials


def print_summary(trials: list[Trial]) -> None:
    print("\nAggregate BER by Pillow recompression quality")
    print("quality,bit_errors,total_bits,ber")
    for quality in QUALITIES:
        group = [trial for trial in trials if trial.quality == quality]
        errors = sum(trial.bit_errors for trial in group)
        bits = sum(trial.embedded_bits for trial in group)
        print(f"{quality},{errors},{bits},{errors / bits:.8f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--covers-dir", required=True)
    parser.add_argument("--output-dir", default="results/local/phase1")
    parser.add_argument("--covers", type=int, default=15)
    parser.add_argument("--bits", type=int, default=512)
    parser.add_argument(
        "--gap", type=int, default=24, help="native coefficient magnitude separation"
    )
    parser.add_argument(
        "--pair-indices",
        default="0,1,2,3",
        help="comma-separated subset of pair positions",
    )
    parser.add_argument("--seed", type=int, default=20260821)
    settings = parser.parse_args()
    print_summary(run(settings))
