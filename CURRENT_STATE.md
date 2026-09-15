# ShadowPost - Current State

## Core System

- Native JPEG DCT embedding uses `jpeglib.read_dct()` and `write_dct()` only.
- Final luminance embedding pairs are positions 0 and 2: `(1,3)` vs `(2,2)`
  and `(1,4)` vs `(4,1)`.
- Extraction tie rule: `|A| >= |B|` decodes as bit `1`.
- Reed-Solomon is fixed at RS(48,32): 32 data bytes and 16 parity bytes.
- AES-256-GCM encrypts each message using a scrypt-derived 32-byte key.
- `app.py` exposes `POST /encode` and `POST /decode`.
- `frontend.html` is the completed browser UI.

## Phase 5 Multi-Platform Benchmark

The canonical dataset `phase5_results/platform_trials.csv` contains 270 rows.
Telegram, Discord, and WhatsApp Document use the structured 15-cover,
three-payload matrix. Twitter/X, Instagram, and WhatsApp Image use 45 fixed
100-byte trials each.

| Platform | Delivery mode | Trials | Success rate | Exact recoveries | Mean recorded BER |
|---|---|---:|---:|---:|---:|
| Discord | Webhook attachment | 45 | 100.0% | 45/45 | 0.00000000 |
| WhatsApp | Document | 45 | 100.0% | 45/45 | 0.00000000 |
| Telegram | `sendPhoto` | 45 | 80.0% | 36/45 | 0.02743540 |
| Twitter / X | Image post | 45 | 0.0% | 0/45 | 1.00000000 |
| Instagram | Feed post | 45 | 0.0% | 0/45 | 1.00000000 |
| WhatsApp | Standard image | 45 | 0.0% | 0/45 | 1.00000000 |
| **Overall** | **All six modes** | **270** | **46.7%** | **126/270** | **0.51727204** |

Mean BER values use recorded rows only; trials rejected before delivery have no
BER value. Discord attachments and WhatsApp documents preserved the stego file
structure. Telegram preserved some payloads but downscaled selected images.
Twitter/X, Instagram, and standard WhatsApp image delivery changed the JPEG
structure through lossy transcoding and spatial scaling.

## Reporting Artifacts

- `phase5_results/platform_trials.csv` - canonical 270-row dataset.
- `phase5_results/*_trials.csv` - platform-specific trial datasets.
- `phase5_results/RESEARCH_SUMMARY.md` - benchmark summary.
- `phase7_charts.py` and `phase7_results/` - charts and numerical summaries.
- `make_ieee_paper.py` and `ShadowPost_IEEE_Paper.pdf` - source and verified
  eight-page, two-column paper.

## Key Implementation Files

- `app.py` - API boundary.
- `phase1_native_dct_experiment.py` - DCT embedding and extraction.
- `phase2_rs_roundtrip.py` - Reed-Solomon validation.
- `phase3_aes_gcm_roundtrip.py` - AES-GCM and RS pipeline.
- `phase5_bench.py` - delivery benchmark support.
- `test_app.py` - API round-trip and capacity checks.
