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
import shutil
from dataclasses import dataclass
from pathlib import Path

import jpeglib
import numpy as np
from PIL import Image


QUALITIES = (95, 90, 80, 70, 60, 50)
# Four disjoint mid-band coefficient pairs per luminance block.  Entries are
# (row_a, col_a, row_b, col_b), and no coefficient is reused within a block.
PAIR_POSITIONS = ((1, 3, 2, 2), (2, 3, 3, 2), (1, 4, 4, 1), (2, 4, 4, 2))


@dataclass(frozen=True)
class Trial:
    cover: str
    quality: int
    embedded_bits: int
    bit_errors: int

    @property
    def ber(self) -> float:
        return self.bit_errors / self.embedded_bits


def random_bits(count: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 2, size=count, dtype=np.uint8)


def luminance_coefficients(jpeg: jpeglib.DCTJPEG) -> np.ndarray:
    """Return the writable native JPEG luminance coefficient tensor."""
    if jpeg.Y is None:
        raise ValueError("JPEG has no luminance (Y) DCT component")
    if jpeg.Y.ndim != 4 or jpeg.Y.shape[-2:] != (8, 8):
        raise ValueError(f"unexpected jpeglib DCT shape: {jpeg.Y.shape}")
    return jpeg.Y


def parse_pair_indices(value: str) -> tuple[int, ...]:
    """Parse a comma-separated subset of the four configured pair positions."""
    indices = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not indices or len(set(indices)) != len(indices) or any(index not in range(len(PAIR_POSITIONS)) for index in indices):
        raise ValueError("pair indices must be a non-empty, unique subset of 0,1,2,3")
    return indices


def usable_pairs(coeffs: np.ndarray, count: int, pair_indices: tuple[int, ...] = (0, 1, 2, 3)) -> list[tuple[int, int, int]]:
    """Choose `count` pair slots as (block_row, block_col, pair_index).

    The block grid is fixed before recompression.  No pixels are touched.
    """
    slots: list[tuple[int, int, int]] = []
    for block_row in range(coeffs.shape[0]):
        for block_col in range(coeffs.shape[1]):
            for pair_index in pair_indices:
                slots.append((block_row, block_col, pair_index))
                if len(slots) == count:
                    return slots
    raise ValueError(f"cover capacity is only {len(slots)} bits, needs {count}")


def set_ordered_pair(block: np.ndarray, pair: tuple[int, int, int, int], bit: int, gap: int) -> None:
    """Embed one bit using the decoder convention |C_a| >= |C_b| => 1.

    Embedding always creates a strict gap. If platform recompression erases
    that gap into an equality, the deterministic tie rule remains bit 1.
    """
    ar, ac, br, bc = pair
    a, b = int(block[ar, ac]), int(block[br, bc])
    sign_a = 1 if a >= 0 else -1
    sign_b = 1 if b >= 0 else -1
    base = max(2, min(abs(a), abs(b)))
    low, high = base, base + gap
    if bit:
        block[ar, ac], block[br, bc] = sign_a * high, sign_b * low
    else:
        block[ar, ac], block[br, bc] = sign_a * low, sign_b * high


def embed_native_dct(source: Path, destination: Path, bits: np.ndarray, gap: int, pair_indices: tuple[int, ...] = (0, 1, 2, 3)) -> None:
    jpeg = jpeglib.read_dct(str(source))
    coeffs = luminance_coefficients(jpeg)
    for bit, (row, col, pair_index) in zip(bits, usable_pairs(coeffs, len(bits), pair_indices), strict=True):
        set_ordered_pair(coeffs[row, col], PAIR_POSITIONS[pair_index], int(bit), gap)
    # This writes the modified coefficient arrays directly; it does not run a
    # spatial-domain JPEG encoder.
    jpeg.write_dct(str(destination))


def extract_native_dct(source: Path, bit_count: int, pair_indices: tuple[int, ...] = (0, 1, 2, 3)) -> np.ndarray:
    jpeg = jpeglib.read_dct(str(source))
    coeffs = luminance_coefficients(jpeg)
    out = np.empty(bit_count, dtype=np.uint8)
    for index, (row, col, pair_index) in enumerate(usable_pairs(coeffs, bit_count, pair_indices)):
        ar, ac, br, bc = PAIR_POSITIONS[pair_index]
        block = coeffs[row, col]
        # Deterministic tie rule: equality decodes as bit 1, matching the
        # non-strict ordering convention documented by set_ordered_pair().
        out[index] = int(abs(int(block[ar, ac])) >= abs(int(block[br, bc])))
    return out


def recompress_with_pillow(source: Path, destination: Path, quality: int) -> None:
    # This is intentionally the only pixel-domain operation: a simulation of
    # platform recompression, after native-DCT embedding is already complete.
    with Image.open(source) as image:
        image.convert("RGB").save(destination, "JPEG", quality=quality, subsampling=0, optimize=False)


def find_covers(covers_dir: Path, count: int) -> list[Path]:
    candidates = sorted(p for p in covers_dir.rglob("*.jpg") if p.is_file())
    candidates += sorted(p for p in covers_dir.rglob("*.jpeg") if p.is_file())
    if len(candidates) < count:
        raise ValueError(f"need {count} JPEG cover images; found {len(candidates)} in {covers_dir}")
    return candidates[:count]


def run(args: argparse.Namespace) -> list[Trial]:
    source_dir = Path(args.covers_dir).resolve()
    out_dir = Path(args.output_dir).resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    pair_indices = parse_pair_indices(args.pair_indices)
    covers = find_covers(source_dir, args.covers)
    payload = random_bits(args.bits, args.seed)
    (out_dir / "payload_sha256.txt").write_text(hashlib.sha256(payload.tobytes()).hexdigest() + "\n", encoding="utf-8")
    (out_dir / "config.json").write_text(json.dumps(vars(args), indent=2) + "\n", encoding="utf-8")

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
            print(f"{cover_id:48.48s} q={quality:2d} errors={errors:4d}/{len(payload)} BER={errors / len(payload):.6f}")

    with (out_dir / "phase1_trials.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("cover", "quality", "embedded_bits", "bit_errors", "ber"))
        writer.writeheader()
        writer.writerows({"cover": t.cover, "quality": t.quality, "embedded_bits": t.embedded_bits,
                          "bit_errors": t.bit_errors, "ber": f"{t.ber:.8f}"} for t in trials)
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
    parser.add_argument("--output-dir", default="phase1_results")
    parser.add_argument("--covers", type=int, default=15)
    parser.add_argument("--bits", type=int, default=512)
    parser.add_argument("--gap", type=int, default=24, help="native coefficient magnitude separation")
    parser.add_argument("--pair-indices", default="0,1,2,3", help="comma-separated subset of pair positions")
    parser.add_argument("--seed", type=int, default=20260821)
    settings = parser.parse_args()
    print_summary(run(settings))
