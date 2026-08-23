# ShadowPost

ShadowPost is a native-JPEG DCT steganography system. It encrypts a message,
protects it with Reed-Solomon error correction, and embeds the resulting bits in
relative DCT coefficient-pair orderings so that the payload can survive some
real-world JPEG delivery transforms.

## Locked pipeline

1. Read and write native JPEG DCT coefficients with `jpeglib.read_dct()` and
   `write_dct()`; embedding never uses pixel-domain DCT.
2. Embed in luminance coefficient-pair positions 0 and 2 only:
   `(1,3)` vs `(2,2)`, and `(1,4)` vs `(4,1)`.
3. Decode ties deterministically: `|A| >= |B|` is bit `1`.
4. Encrypt the whole message once with AES-256-GCM using a scrypt-derived key.
   Frame `[2-byte length][12-byte nonce][ciphertext][16-byte tag]`, then split
   into RS data chunks.
5. Use fixed RS(48,32): 32 data bytes plus 16 parity bytes per codeword.

## Quickstart

```bash
pip install -r requirements-phase1.txt
uvicorn app:app --port 8000
```

Open `frontend.html` in a browser for the dependency-free Encode/Decode UI.

## HTTP API

| Endpoint | Form fields | Returns |
|---|---|---|
| `POST /encode` | `cover`, `message`, `passphrase` | Stego JPEG and `X-ShadowPost-Max-Bytes` |
| `POST /decode` | `stego`, `passphrase` | Recovered `message` JSON |

Capacity is computed from the uploaded JPEG's luminance DCT block grid.
Over-capacity messages and failed decode/authentication attempts return HTTP 400
with a descriptive error.

## Phase 5 platform delivery bench

`phase5_bench.py` runs the exact 15 Phase 1 covers at 10-byte, 100-byte, and
near-capacity payload sizes for Telegram and Discord. It obtains credentials
from the process environment or an ignored local `.env`; credentials are never
written to results.

The completed matrix in `phase5_results/platform_trials.csv` contains 90 trials:

| Platform | Exact recoveries |
|---|---:|
| Telegram | 36/45 (80.0%) |
| Discord | 45/45 (100.0%) |

Telegram `sendPhoto` is not byte-preserving. A measured arsenal delivery changed
an 864x864 stego JPEG to 800x800, reducing its luminance DCT grid from 108x108 to
100x100 blocks (23,328 to 20,000 usable payload bits). Discord webhook delivery
was byte-preserving in the completed matrix.

Future bench rows include source and delivered width/height fields, in addition
to platform, trial, cover, payload size, BER, outcome, reason, and timestamp.
Imgur is pending. Reddit remains out of scope without pre-existing OAuth
credentials.

`manual_platform_test.py` supports a prepare/upload/check workflow when a manual
platform test is needed.

## Phase 7 reporting

Run:

```bash
python phase7_charts.py
```

The script reads the 90-row Phase 5 CSV and writes four 150-DPI PNG charts plus
`summary.txt` to `phase7_results/`:

- Success rate per platform
- Success rate by small, medium, and near-max payload class
- Success rate per cover image
- Overall success/failure summary

## Repository layout

| Path | Purpose |
|---|---|
| `app.py` | FastAPI `/encode` and `/decode` service |
| `frontend.html` | Dependency-free browser client |
| `test_app.py` | FastAPI TestClient checks |
| `phase1_native_dct_experiment.py` | Final native-DCT embed/extract experiment |
| `phase2_rs_roundtrip.py` | RS(48,32) experiment |
| `phase3_aes_gcm_roundtrip.py` | AES-256-GCM + RS experiment |
| `phase5_bench.py` | Telegram/Discord delivery bench |
| `phase5_results/platform_trials.csv` | Completed 90-trial platform matrix |
| `phase7_charts.py`, `phase7_results/` | Charts and numerical summary |

## Security

The app does not persist plaintext messages or passphrases. Bench output stores
only trial metadata, dimensions, BER, results, and timestamps. `run_trials.bat`
and `.env` are ignored because they contain live platform credentials.
