# ShadowPost — Current State

## Complete: Phases 1–4

- Native JPEG DCT embedding via `jpeglib.read_dct()` / `write_dct()`.
- Final embedding uses luminance-block coefficient-pair positions **0** and **2** only:
  - Position 0: `(1,3)` vs `(2,2)`
  - Position 2: `(1,4)` vs `(4,1)`
  - Deterministic extraction tie-break: `|A| >= |B|` decodes as bit `1`.
- Reed–Solomon is fixed at **RS(48,32)**: 32 data bytes and 16 parity bytes.
- Encryption is AES-256-GCM. A 32-byte key is derived from the passphrase with scrypt.
  The API encrypts the entire message once, with a single fresh 12-byte nonce and one 16-byte tag,
  then frames `[2-byte length][nonce][ciphertext][tag]` before splitting it into 32-byte RS chunks.
- FastAPI endpoints:
  - `POST /encode`: uploaded JPEG + plaintext + passphrase -> stego JPEG; reports image-specific capacity errors as HTTP 400.
  - `POST /decode`: uploaded stego JPEG + passphrase -> decrypted plaintext or a clear decoding error.
- TestClient round-trip and over-capacity HTTP-400 tests pass.

## Next: Phase 5

Build the Telegram then Discord upload/download test bench, log results to CSV, and add Imgur via Client-ID.
Reddit remains skipped unless pre-existing OAuth credentials are supplied, per the access policy.

## Key Artifacts

- `phase1_native_dct_experiment.py` — finalized DCT embedding/extraction and Phase 1 experiment.
- `phase1_results_positions_0_2_tie_fixed/phase1_trials.csv` — final 0/2 Phase 1 results.
- `phase2_rs_roundtrip.py` — RS(48,32) round-trip experiment.
- `phase2_rs_results/phase2_rs_trials.csv` — Phase 2 results.
- `phase3_aes_gcm_roundtrip.py` — AES-256-GCM + RS Phase 3 experiment.
- `phase3_aes_gcm_results/phase3_trials.csv` — Phase 3 results.
- `app.py` — FastAPI Phase 4 service.
- `test_app.py` — FastAPI TestClient checks.
- `requirements-phase1.txt` — pinned project dependencies.
