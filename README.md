# ShadowPost

DCT-domain image steganography that hides AES-encrypted messages inside native
JPEG frequency coefficients, designed to survive real-world recompression by
social platforms (Telegram, Discord, Imgur). Reed–Solomon error correction
repairs bit errors introduced when a platform re-encodes the image.

## How it works

1. **Embedding** operates on native JPEG DCT coefficients via `jpeglib`
   (`read_dct` / `write_dct`) — never on pixels — so the payload survives the
   JPEG encoder untouched.
2. Bits are encoded as the relative magnitude ordering of mid-band coefficient
   **pairs** within each 8x8 luminance block (2 bits per block), using
   positions **0 and 2** only, with a deterministic tie-break
   (`|A| >= |B|` -> bit `1`).
3. The message is framed as `[2-byte length][12-byte nonce][ciphertext][16-byte tag]`,
   encrypted once with **AES-256-GCM** (key derived from the passphrase via scrypt),
   split into 32-byte chunks, and each chunk is protected by **RS(48,32)**
   (corrects up to 8 byte errors per codeword).

These parameters are locked; see `CURRENT_STATE.md` for details.

## Quickstart

```bash
pip install -r requirements-phase1.txt
uvicorn app:app --port 8000
```

Then open `frontend.html` directly in any browser (no build step, no server
needed for it) or serve it however you like.

## Web frontend

`frontend.html` is a single self-contained file (plain HTML/CSS/JS, zero
dependencies):

- **Encode tab** — pick a cover JPEG, type the secret message and a passphrase,
  click Encode. The stego JPEG downloads automatically; the banner also shows
  the image's exact byte capacity reported by the API.
- **Decode tab** — upload a stego JPEG, enter the same passphrase, click Decode.
  The recovered message is shown on screen.
- API errors (HTTP 400) are displayed verbatim in a red banner; if the backend
  is not running you get an explicit "cannot reach localhost:8000" message.

## HTTP API

| Endpoint        | Form fields                     | Returns                                        |
|-----------------|---------------------------------|------------------------------------------------|
| `POST /encode`  | `cover` (file), `message`, `passphrase` | stego JPEG + `X-ShadowPost-Max-Bytes` header |
| `POST /decode`  | `stego` (file), `passphrase`    | `{"message": "..."}`                           |

Capacity is computed per image from its actual block count; over-capacity
messages and undecodable images return HTTP 400 with a descriptive detail.

## Platform test bench (Phase 5)

- `phase5_bench.py` — automated Telegram / Discord / Imgur round trips
  (credentials read from `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`,
  `DISCORD_WEBHOOK_URL`, `IMGUR_CLIENT_ID` env vars; never logged).
- `manual_platform_test.py` — manual workflow:
  ```bash
  python manual_platform_test.py prepare --platform telegram --cover <cover.jpg> --message "hi" --passphrase "pw"
  # upload phase5_results/manual_upload/telegram.jpg by hand, download the delivered file, then:
  python manual_platform_test.py check --platform telegram --downloaded-image <downloaded.jpg> --passphrase "pw"
  ```
- All trials append to `phase5_results/platform_trials.csv`.

## Reporting charts (Phase 7)

After trials are complete:

```bash
python phase7_charts.py
```

Writes to `phase7_results/`: success rate per platform, average BER per
platform, and max embedded payload per cover image (bar chart + table).

## Repository layout

| Path | Purpose |
|------|---------|
| `app.py` | FastAPI service (`/encode`, `/decode`) |
| `frontend.html` | Browser UI |
| `test_app.py` | TestClient round-trip and HTTP-400 checks |
| `phase1_native_dct_experiment.py` | Finalized DCT embed/extract + Phase 1 experiment |
| `phase2_rs_roundtrip.py` | RS(48,32) round-trip experiment |
| `phase3_aes_gcm_roundtrip.py` | AES-256-GCM + RS experiment |
| `phase5_bench.py`, `manual_platform_test.py` | Platform delivery testing |
| `phase7_charts.py` | Result charts |
| `phase*_results*/` | Experiment data |
| `CURRENT_STATE.md` | Detailed technical state |

Reddit delivery was skipped by policy unless pre-existing OAuth credentials are supplied.

## Security notes

The passphrase never leaves your machine in plaintext form beyond the local
API call; nothing is persisted by the app. Bench scripts store only cover
names, sizes, BERs, and timestamps — never passphrases or plaintexts.
