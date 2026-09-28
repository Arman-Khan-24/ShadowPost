<div align="center">

# 🛡️ ShadowPost

### Adaptive Native-JPEG DCT Steganography Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Cryptography](https://img.shields.io/badge/Crypto-AES--256--GCM%20%7C%20scrypt-success.svg)](https://cryptography.io)
[![FEC](https://img.shields.io/badge/FEC-Reed--Solomon%20RS(48%2C32)-orange.svg)](https://en.wikipedia.org/wiki/Reed%E2%80%93Solomon_error_correction)
[![Status](https://img.shields.io/badge/Evaluated-270%20Live%20Trials-indigo.svg)](#benchmark-results)

**ShadowPost** is an end-to-end, channel-adaptive image steganography platform engineered to survive the lossy compression, spatial resampling, and progressive transcoding pipelines of modern social media networks (*Instagram, Twitter/X, Telegram, Discord, and WhatsApp*).

[Live Demo](#quickstart) • [Architecture](#system-architecture) • [Platform Profiles](#adaptive-platform-profiles) • [Research Benchmark](#benchmark-results) • [API Reference](#api-documentation)

---

<img src="docs/shadowpost_hero.png" alt="ShadowPost Web UI" width="900" style="border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.15);" />

</div>

---

## 📌 The Problem & Innovation

### The Traditional Stego Failure
Traditional steganography relies on **Spatial-Domain LSB (Least Significant Bit)** manipulation. When an image is uploaded to platforms like Instagram or Twitter/X:
1. **Aggressive Recompression:** High-frequency DCT quantization zeroes out low-significance pixel perturbations.
2. **Spatial Resampling & Grid Shift:** Platforms downscale oversized images (e.g. 4K down to 1080px), shifting the $8\times 8$ Discrete Cosine Transform (DCT) block lattice and destroying unaligned spatial data completely.

### The ShadowPost Solution
ShadowPost replaces fragile spatial embedding with a **tri-layer defense**:
1. **Adaptive Canvas Pre-Flight:** Pre-conditions cover geometry to the target platform’s native ingestion canvas (e.g., $1080\times 1080$ for Instagram) snapped to multiples of 16, eliminating fractional spatial downsampling by platform servers.
2. **Native-JPEG DCT Frequency Embedding:** Manipulates the relative magnitude orderings ($|A| \ge |B|$) of mid-frequency luminance DCT coefficient pairs directly via `jpeglib` without decoding to pixels.
3. **Cryptographic & Error Correction Armor:** 
   - **`scrypt`** memory-hard key derivation resistant to GPU brute-force attacks.
   - **`AES-256-GCM`** authenticated encryption with fresh 96-bit nonces (guarantees binary success and zero false positives).
   - **`Reed-Solomon RS(48,32)`** forward error correction to autonomously heal bit-flips caused by platform quantization noise.

---

## 📸 Platform Interface

<div align="center">
  <img src="docs/shadowpost_full.png" alt="Platform Channels and Features" width="850" style="border-radius: 8px; margin-bottom: 20px;" />
</div>

---

## ⚡ Adaptive Platform Profiles

| Target Channel | Strategy & Canvas | DCT Gap | FEC Code | Use Case |
| :--- | :--- | :---: | :---: | :--- |
| **Instagram Feed** | Strict 1080×1080 square canvas, Q=80 pre-quantization | `36` | `RS(48,32)` | Survives Meta's aggressive feed transcode |
| **Twitter / X Post** | Max width ≤1200px, Huffman baseline table enforcement | `32` | `RS(48,32)` | Survives X desktop/mobile web delivery |
| **Telegram Photo** | Max bounds ≤1280px (divisible by 16), Q=85 pre-save | `28` | `RS(48,32)` | Survives standard `sendPhoto` compression |
| **Lossless Channel** | Native bounds preserved, byte-level bit preservation | `24` | `RS(48,32)` | Discord attachments & WhatsApp Document |

---

## 🔬 Benchmark Results (270 Real-World Trials)

Empirical survivability across 270 automated and live-platform delivery trials:

| Platform | Channel Mode | Trials | Exact Recovery | Success Rate | Mean BER | Observed Behavior |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Discord** | Webhook Attachment | 45 | 45 | **100.0%** | `0.0000` | Full bit-preserving transfer |
| **WhatsApp** | Document Mode | 45 | 45 | **100.0%** | `0.0000` | Byte-level preservation |
| **Telegram** | `sendPhoto` | 45 | 36 | **80.0%** | `0.0274` | Survives when canvas bounds align |
| **Instagram** | Live Feed Post | 45 | 45* | **Adaptive Ready** | `0.0000` | **100% verified** using Adaptive Engine |
| **Twitter / X** | Live Feed Post | 45 | 45* | **Adaptive Ready** | `0.0000` | **100% verified** via original resolution ingest |

*\*Adaptive profile validation tested live on delivered feed derivatives.*

---

## 🛠️ System Architecture

```
[Plaintext Secret] + [Passphrase]
         │
         ▼
1. Memory-Hard KDF: scrypt(N=16384, r=8, p=1) ──► 256-bit Key
         │
         ▼
2. Authenticated Encryption: AES-256-GCM ──► Ciphertext + Nonce(12B) + AuthTag(16B)
         │
         ▼
3. Error Correction Armor: Reed-Solomon RS(48,32) ──► 16 Parity Bytes per 32B data
         │
         ▼
4. Adaptive Pre-Flight: Canvas Snapping + Baseline Re-quantization
         │
         ▼
5. Native DCT Embedding: Mid-frequency relative pairs (1,3) vs (2,2) & (1,4) vs (4,1)
         │
         ▼
   [Stego JPEG] ──► Uploaded to Social Platform ──► Transmitted / Delivered
         │
         ▼
6. Extraction & Decoding:
   Read DCT Grid ──► Relative Order Decode ──► RS Error Repair ──► AES-GCM Tag Verify
         │
         ▼
[Authenticated Original Plaintext]
```

---

## 🚀 Quickstart

### Prerequisites
* Python 3.10+
* `pip`

### 1. Clone & Install
```bash
git clone https://github.com/Arman-Khan-24/ShadowPost.git
cd ShadowPost
pip install -r requirements-phase1.txt
```

### 2. Launch the Application
```bash
uvicorn app:app --port 8000 --reload
```
Open **`http://127.0.0.1:8000`** in your browser to access the full web application.

---

## 📡 API Documentation

### `POST /encode`
Encodes and armors a secret message into a cover JPEG according to the chosen platform profile.

**Parameters (multipart/form-data):**
* `cover`: JPEG image file (`image/jpeg`)
* `message`: Text message to hide
* `passphrase`: Secret encryption key
* `platform`: Target profile (`instagram`, `twitter`, `telegram`, `default`)

**Response:**
* Binary JPEG stream (`image/jpeg`)
* Headers:
  * `X-ShadowPost-Platform`: Applied profile
  * `X-ShadowPost-Dimensions`: Resized/conditioned canvas (e.g. `1080x1080`)
  * `X-ShadowPost-Max-Bytes`: Maximum payload capacity

---

### `POST /decode`
Extracts, repairs, and cryptographically authenticates the secret payload from any delivered image.

**Parameters (multipart/form-data):**
* `stego`: Stego JPEG file (`image/jpeg`)
* `passphrase`: Decryption passphrase

**Response (JSON):**
```json
{
  "message": "Top secret meeting at 0800 hours."
}
```

---

### `GET /paper`
Serves the verified 7-page IEEE-style research paper:
* **Route:** `http://127.0.0.1:8000/paper`
* **Filename:** `ShadowPost_IEEE_Paper.pdf`

---

## 👥 Contributors & Academic Reference

Developed as an advanced engineering and security research project at **Priyadarshini College of Engineering (PCE), Nagpur**.

* **Arman Rizwan Khan** (Lead Developer & Author)
* **Shreya Kamlesh Prasad**
* **Divyani Dinkar Waikar**
* **Aryan Manoj Terha**
* **Aditya Pravin Shakya**
* **Prof. Rajshri Pote** (Project Guide)

For detailed mathematical error models, capacity proofs, and experimental datasets, refer to [ShadowPost_IEEE_Paper.pdf](ShadowPost_IEEE_Paper.pdf).
