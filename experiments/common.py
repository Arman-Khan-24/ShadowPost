"""Shared experiment fixtures and Pillow recompression simulation."""

from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image
from shadowpost.dct_codec import PAIR_POSITIONS

QUALITIES = (95, 90, 80, 70, 60, 50)


def random_bits(count: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 2, size=count, dtype=np.uint8)


def parse_pair_indices(value: str) -> tuple[int, ...]:
    """Parse a comma-separated subset of the four configured pair positions."""
    indices = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if (
        not indices
        or len(set(indices)) != len(indices)
        or any(index not in range(len(PAIR_POSITIONS)) for index in indices)
    ):
        raise ValueError("pair indices must be a non-empty, unique subset of 0,1,2,3")
    return indices


def recompress_with_pillow(source: Path, destination: Path, quality: int) -> None:
    # This is intentionally the only pixel-domain operation: a simulation of
    # platform recompression, after native-DCT embedding is already complete.
    with Image.open(source) as image:
        image.convert("RGB").save(
            destination, "JPEG", quality=quality, subsampling=0, optimize=False
        )


def find_covers(covers_dir: Path, count: int) -> list[Path]:
    candidates = sorted(p for p in covers_dir.rglob("*.jpg") if p.is_file())
    candidates += sorted(p for p in covers_dir.rglob("*.jpeg") if p.is_file())
    if len(candidates) < count:
        raise ValueError(
            f"need {count} JPEG cover images; found {len(candidates)} in {covers_dir}"
        )
    return candidates[:count]


def classify_failure(exc: Exception) -> str:
    message = str(exc).lower()
    if "capacity" in message or "too few blocks" in message:
        return "capacity_failure"
    if "reedsolomon" in message or "reed-solomon" in message:
        return "reed_solomon_decode_failed"
    if "authenticate" in message or "gcm" in message:
        return "authentication_failed"
    return "fixed_grid_extraction_failed"
