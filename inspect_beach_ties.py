"""Read-only inspection of beach failures from the existing refined Phase 1 run."""

from pathlib import Path

import jpeglib
import numpy as np

from phase1_native_dct_experiment import PAIR_POSITIONS, luminance_coefficients, random_bits, usable_pairs


RESULTS = Path("phase1_results_positions_0_2_tie_fixed")
BITS = random_bits(256, 20260821)
SLOTS = usable_pairs(luminance_coefficients(jpeglib.read_dct(str(RESULTS / "03_preview_stego.jpg"))), 256, (0, 2))

for quality in (95, 90, 80, 70, 60, 50):
    coeffs = luminance_coefficients(jpeglib.read_dct(str(RESULTS / f"03_preview_q{quality}.jpg")))
    for index, (row, col, pair_index) in enumerate(SLOTS):
        ar, ac, br, bc = PAIR_POSITIONS[pair_index]
        a, b = int(coeffs[row, col, ar, ac]), int(coeffs[row, col, br, bc])
        decoded = int(abs(a) >= abs(b))
        if decoded != int(BITS[index]):
            print(f"q={quality} bit={index} pair_position={pair_index} expected={int(BITS[index])} "
                  f"A={a} B={b} |A|={abs(a)} |B|={abs(b)} tie={abs(a) == abs(b)}")
