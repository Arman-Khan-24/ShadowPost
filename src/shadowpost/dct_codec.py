"""Direct libjpeg DCT coefficient access and relative-pair encoding."""

from __future__ import annotations
from pathlib import Path
import jpeglib
import numpy as np

# Four disjoint mid-band coefficient pairs per luminance block.  Entries are
# (row_a, col_a, row_b, col_b), and no coefficient is reused within a block.
PAIR_POSITIONS = ((1, 3, 2, 2), (2, 3, 3, 2), (1, 4, 4, 1), (2, 4, 4, 2))


def luminance_coefficients(jpeg: jpeglib.DCTJPEG) -> np.ndarray:
    """Return the writable native JPEG luminance coefficient tensor."""
    if jpeg.Y is None:
        raise ValueError("JPEG has no luminance (Y) DCT component")
    if jpeg.Y.ndim != 4 or jpeg.Y.shape[-2:] != (8, 8):
        raise ValueError(f"unexpected jpeglib DCT shape: {jpeg.Y.shape}")
    return jpeg.Y


def usable_pairs(
    coeffs: np.ndarray, count: int, pair_indices: tuple[int, ...] = (0, 1, 2, 3)
) -> list[tuple[int, int, int]]:
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


def set_ordered_pair(
    block: np.ndarray, pair: tuple[int, int, int, int], bit: int, gap: int
) -> None:
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


def embed_native_dct(
    source: Path,
    destination: Path,
    bits: np.ndarray,
    gap: int,
    pair_indices: tuple[int, ...] = (0, 1, 2, 3),
) -> None:
    jpeg = jpeglib.read_dct(str(source))
    coeffs = luminance_coefficients(jpeg)
    for bit, (row, col, pair_index) in zip(
        bits, usable_pairs(coeffs, len(bits), pair_indices), strict=True
    ):
        set_ordered_pair(coeffs[row, col], PAIR_POSITIONS[pair_index], int(bit), gap)
    # This writes the modified coefficient arrays directly; it does not run a
    # spatial-domain JPEG encoder.
    jpeg.write_dct(str(destination))


def extract_native_dct(
    source: Path, bit_count: int, pair_indices: tuple[int, ...] = (0, 1, 2, 3)
) -> np.ndarray:
    jpeg = jpeglib.read_dct(str(source))
    coeffs = luminance_coefficients(jpeg)
    out = np.empty(bit_count, dtype=np.uint8)
    for index, (row, col, pair_index) in enumerate(
        usable_pairs(coeffs, bit_count, pair_indices)
    ):
        ar, ac, br, bc = PAIR_POSITIONS[pair_index]
        block = coeffs[row, col]
        # Deterministic tie rule: equality decodes as bit 1, matching the
        # non-strict ordering convention documented by set_ordered_pair().
        out[index] = int(abs(int(block[ar, ac])) >= abs(int(block[br, bc])))
    return out
