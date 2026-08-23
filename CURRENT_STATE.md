# ShadowPost - Current State

## Complete: Phases 1-7

- Native JPEG DCT embedding uses `jpeglib.read_dct()` and `write_dct()` only.
- Final luminance embedding pairs are positions 0 and 2:
  `(1,3)` vs `(2,2)` and `(1,4)` vs `(4,1)`.
- Extraction tie rule: `|A| >= |B|` decodes as bit `1`.
- Reed-Solomon is fixed at RS(48,32): 32 data bytes and 16 parity bytes.
- AES-256-GCM encrypts each entire message once using a scrypt-derived 32-byte
  key. The container is `[2-byte length][12-byte nonce][ciphertext][16-byte tag]`,
  then split into 32-byte RS data chunks.
- `app.py` exposes `POST /encode` and `POST /decode`. Capacity is image-specific;
  TestClient round-trip and over-capacity checks pass.
- `frontend.html` is the completed Phase 6 single-file browser UI.

## Phase 5 completed results

- `phase5_bench.py` is committed and runs the exact 15 Phase 1 covers listed in
  `phase1_results_positions_0_2_tie_fixed/phase1_trials.csv`.
- The complete Telegram/Discord matrix has 90 rows: 15 covers x 10 B, 100 B, and
  near-capacity payloads x 2 platforms.
- Telegram recovered 36/45 messages (80.0%); Discord recovered 45/45 (100.0%).
- Future rows log `cover_width`, `cover_height`, `delivered_width`, and
  `delivered_height` to make delivery transformations measurable.
- Telegram `sendPhoto` is not byte-preserving. A direct arsenal measurement
  changed 864x864 to 800x800 and the luminance DCT grid from 108x108 to 100x100.
  This changes usable payload capacity from 23,328 to 20,000 bits.
- Corsair is structurally exceptional: its cover is 3840x2160, while the other
  Phase 1 covers are 512-1152px on their longest side. Telegram resampling loses
  the original DCT block registration and gives about 50% BER even at 10 B and
  100 B. This is a delivery-resampling limitation, not an embedding, RS, or AES
  parameter issue.
- Imgur is pending. Reddit remains skipped unless pre-existing OAuth credentials
  are supplied.

## Phase 7 completed results

`phase7_results/` contains four 150-DPI charts and `summary.txt`, produced from
the clean 90-row CSV:

- 81/90 exact recoveries overall (90.0%)
- Telegram: 36/45 (80.0%)
- Discord: 45/45 (100.0%)

## Next

Choose a Telegram payload policy based on measured delivered dimensions before
running more platform trials. Do not change the locked DCT, RS, or AES
parameters without a new empirical validation phase.

## Key artifacts

- `phase1_native_dct_experiment.py` - finalized DCT embedding/extraction.
- `phase1_results_positions_0_2_tie_fixed/phase1_trials.csv` - final Phase 1
  cover manifest and BER results.
- `phase2_rs_roundtrip.py` and `phase2_rs_results/` - RS(48,32) validation.
- `phase3_aes_gcm_roundtrip.py` and `phase3_aes_gcm_results/` - AES-GCM
  validation.
- `app.py`, `test_app.py`, and `frontend.html` - Phase 4 API and Phase 6 UI.
- `phase5_bench.py` and `phase5_results/platform_trials.csv` - delivery bench.
- `phase7_charts.py` and `phase7_results/` - reports and charts.
- `requirements-phase1.txt` - pinned dependencies.
