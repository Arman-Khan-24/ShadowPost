# ShadowPost

ShadowPost is a native-JPEG DCT steganography system. It encrypts a message,
protects it with Reed-Solomon error correction, and embeds the resulting bits in
relative DCT coefficient-pair orderings for evaluation across real-world social
media and messaging delivery channels.

## Locked Pipeline

1. Read and write native JPEG DCT coefficients with `jpeglib.read_dct()` and
   `write_dct()`; embedding never uses pixel-domain DCT.
2. Embed in luminance coefficient-pair positions 0 and 2 only: `(1,3)` vs
   `(2,2)`, and `(1,4)` vs `(4,1)`.
3. Decode ties deterministically: `|A| >= |B|` is bit `1`.
4. Encrypt the whole message once with AES-256-GCM using a scrypt-derived key.
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
| `POST /decode` | `stego`, `passphrase` | Recovered message JSON |

Capacity is computed from the uploaded JPEG's luminance DCT block grid.

## Phase 5 Multi-Platform Benchmark

The canonical dataset `phase5_results/platform_trials.csv` contains 270 rows.
The structured cohort contains 15 covers and three payload classes for Telegram,
Discord, and WhatsApp Document. The feed/media cohort contains 45 fixed 100-byte
trials for Twitter/X, Instagram, and WhatsApp Image.

| Platform | Delivery mode | Trials | Success rate | Exact recoveries | Mean recorded BER |
|---|---|---:|---:|---:|---:|
| Discord | Webhook attachment | 45 | 100.0% | 45/45 | 0.00000000 |
| WhatsApp | Document | 45 | 100.0% | 45/45 | 0.00000000 |
| Telegram | `sendPhoto` | 45 | 80.0% | 36/45 | 0.02743540 |
| Twitter / X | Image post | 45 | 0.0% | 0/45 | 1.00000000 |
| Instagram | Feed post | 45 | 0.0% | 0/45 | 1.00000000 |
| WhatsApp | Standard image | 45 | 0.0% | 0/45 | 1.00000000 |
| **Overall** | **All six modes** | **270** | **46.7%** | **126/270** | **0.51727204** |

The BER column is the mean of recorded BER values; capacity-rejected trials have
no BER value and are excluded from that mean. The outcomes describe the tested
delivery modes for the recorded account, client, and dates. The stored manual
rows do not contain enough metadata to quantify a particular platform transform.

## Phase 7 Reporting

```bash
python phase7_charts.py
```

The script reads the Phase 5 dataset and writes charts and summaries to
`phase7_results/`.

## Repository Layout

| Path | Purpose |
|---|---|
| `app.py` | FastAPI `/encode` and `/decode` service |
| `frontend.html` | Dependency-free browser client |
| `test_app.py` | FastAPI TestClient checks |
| `phase1_native_dct_experiment.py` | Native-DCT embedding and extraction |
| `phase5_results/platform_trials.csv` | Canonical 270-row matrix |
| `phase5_results/*_trials.csv` | Platform-specific datasets |
| `phase7_charts.py`, `phase7_results/` | Reports and charts |
| `downloaded/` | Downloaded Twitter and Instagram trial images |
| `make_ieee_paper.py` | Generates the two-column IEEE-style paper |
| `ShadowPost_IEEE_Paper.pdf` | Seven-page, two-column IEEE-style research paper |

## Security

The app does not persist plaintext messages or passphrases. Bench output stores
trial metadata, dimensions, BER, results, and timestamps.

The canonical CSV contains source and delivered dimension columns for automated
trials; historical manually recorded rows leave those fields empty. Failure
labels use the reproducible classes `fixed_grid_extraction_failed`,
`reed_solomon_decode_failed`, `capacity_failure`, and `authentication_failed`.
The six delivery modes are a descriptive snapshot of the tested account, client,
and date configurations, not a universal platform ranking.
