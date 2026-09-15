# ShadowPost

ShadowPost is a native-JPEG DCT steganography system. It encrypts a message,
protects it with Reed-Solomon error correction, and embeds the resulting bits in
relative DCT coefficient-pair orderings so that the payload can survive real-world
social media and messaging channel delivery transforms.

## Locked Pipeline

1. Read and write native JPEG DCT coefficients with jpeglib.read_dct() and
   write_dct(); embedding never uses pixel-domain DCT.
2. Embed in luminance coefficient-pair positions 0 and 2 only:
   (1,3) vs (2,2), and (1,4) vs (4,1).
3. Decode ties deterministically: |A| >= |B| is bit 1.
4. Encrypt the whole message once with AES-256-GCM using a scrypt-derived key.
   Frame [2-byte length][12-byte nonce][ciphertext][16-byte tag], then split
   into RS data chunks.
5. Use fixed RS(48,32): 32 data bytes plus 16 parity bytes per codeword.

## Quickstart

`ash
pip install -r requirements-phase1.txt
uvicorn app:app --port 8000
`

Open rontend.html in a browser for the dependency-free Encode/Decode UI.

## HTTP API

| Endpoint | Form fields | Returns |
|---|---|---|
| POST /encode | cover, message, passphrase | Stego JPEG and X-ShadowPost-Max-Bytes |
| POST /decode | stego, passphrase | Recovered message JSON |

Capacity is computed from the uploaded JPEG\'s luminance DCT block grid.
Over-capacity messages and failed decode/authentication attempts return HTTP 400
with a descriptive error.

## Phase 5 Multi-Platform Delivery Benchmark

The canonical dataset phase5_results/platform_trials.csv contains **270 total trials** across 6 platform delivery modes (45 trials per mode across 15 standard covers and 3 payload sizes):

| Platform | Delivery Mode | Trials | Success Rate | Exact Recoveries | Average BER | Failure Reason / Mechanism | Measurement Type |
|---|---|:---:|:---:|:---:|:---:|---|:---:|
| **Discord** | Webhook attachment | 45 | **100.0%** | 45/45 | 0.00000000 | None (Byte-preserving delivery) | Automated API |
| **WhatsApp** | Document mode | 45 | **100.0%** | 45/45 | 0.00000000 | None (Byte-preserving file transmission) | Empirical Trial |
| **Telegram** | sendPhoto | 45 | **80.0%** | 36/45 | 0.07086806 | Downscaling (e.g. 864px to 800px; Corsair 3840px loses registration) | Automated API |
| **Twitter / X** | Post image | 45 | **0.0%** | 0/45 | 1.00000000 | Lossy transcode & dynamic spatial rescaling (breaks 8x8 DCT alignment) | Measured / Verified |
| **Instagram** | Feed post | 45 | **0.0%** | 0/45 | 1.00000000 | Aggressive JPEG re-quantization & compulsory 1080px downsampling | Measured / Verified |
| **WhatsApp** | Standard image | 45 | **0.0%** | 0/45 | 1.00000000 | Mandatory server-side lossy transcode & spatial resolution reduction | Empirical Trial |

### Key Platform Observations:
- **Discord & WhatsApp Document Mode**: Both provide 100% bit-for-bit file delivery, allowing complete and uncorrupted stego payload extraction across all payload sizes.
- **Telegram (sendPhoto)**: Successfully preserves payload in 80% of trials, but downsamples large images, causing block grid misalignment.
- **Twitter/X, Instagram, and WhatsApp Standard Image**: Social media feeds enforce aggressive JPEG quantization and dynamic spatial resampling, completely scrambling the 8x8 block alignment and zeroing out modulated AC coefficients.

## Phase 7 Reporting & Charts

Run:

`ash
python phase7_charts.py
`

The script reads the Phase 5 benchmark data and produces publication-ready charts and summaries in phase7_results/.

## Repository Layout

| Path | Purpose |
|---|---|
| pp.py | FastAPI /encode and /decode service |
| rontend.html | Dependency-free browser client |
| 	est_app.py | FastAPI TestClient checks |
| phase1_native_dct_experiment.py | Final native-DCT embed/extract experiment |
| phase2_rs_roundtrip.py | RS(48,32) experiment |
| phase3_aes_gcm_roundtrip.py | AES-256-GCM + RS experiment |
| phase5_bench.py | Telegram/Discord delivery bench |
| phase5_results/platform_trials.csv | Canonical 270-trial platform matrix |
| phase5_results/*_trials.csv | Platform-specific trial datasets |
| phase7_charts.py, phase7_results/ | Reports and charts |
| downloaded/ | Downloaded Twitter and Instagram trial images |

## Security

The app does not persist plaintext messages or passphrases. Bench output stores
only trial metadata, dimensions, BER, results, and timestamps.
