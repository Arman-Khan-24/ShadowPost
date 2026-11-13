# Current state

Updated: 13 November 2026. ShadowPost is an in-progress native-JPEG steganography research project, not production-ready software. [README.md](README.md) is the main setup, usage, and platform-status reference.

## Implementation

The core lives under `src/shadowpost/`: `crypto.py`, `ecc.py`, `dct_codec.py`, `pipeline.py`, and `profiles.py`. `api.py` contains the FastAPI boundary; root `app.py` exposes the ASGI application. Application framing, KDF salt, RS(48,32), pair indices `(0,2)`, coefficient gap `6`, and existing profile values are preserved by the restructure.

`web/index.html` is the browser interface. `tests/test_app.py` covers API round trips, conditioning, capacity errors, invalid input, incorrect passwords, and damaged JPEGs. Research entry points live under `experiments/` and `scripts/`; invoke them as modules from the repository root.

## Delivery status

The author reports manual retesting across all six delivery modes on 13 November 2026: Discord attachments, WhatsApp documents, Telegram images, Twitter/X images, and Instagram images recovered messages. **WhatsApp Image mode still fails and remains an open limitation.**

The recorded August–September 2026 delivery study is preserved in `results/phase5/`; its exact numerical findings are documented in [results/README.md](results/README.md). The paper and generated figures describe that recorded study.

## Research artifacts

- `results/phase1*`, `results/phase2_rs/`, `results/phase3_aes_gcm/`: original DCT/ECC/encryption trials and artifacts.
- `results/phase5/`: canonical delivery CSV, platform-specific CSVs, and historical summary.
- `results/phase7/`, `results/offline_analysis/`: recorded numerical summaries and charts.
- `results/downloaded/`: retained delivered media.
- `research/papers/`, `research/figures/`: archived paper, LaTeX source, and figures.
- `results/local/`: ignored outputs from new local runs; historical datasets are not overwritten by default.

Runtime dependencies are in `requirements.txt`; tests and research tools use `requirements-dev.txt`. `pyproject.toml` installs the `src/` package. Credentials stay in ignored `.env` files; the local platform batch runner remains ignored.
