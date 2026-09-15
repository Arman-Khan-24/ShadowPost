# ShadowPost: Empirical Multi-Platform Survivability Study
## Research Benchmark Summary Report

### 1. Abstract & Experimental Design
This study benchmarks the survivability of native-JPEG Discrete Cosine Transform (DCT) steganography combined with Reed-Solomon RS(48,32) error correction and AES-256-GCM authenticated encryption across six real-world social media and instant messaging transmission pipelines.

A standard test matrix comprising 15 diverse cover images across 3 payload sizes (10 B, 100 B, and near-maximum capacity) was subjected to delivery across each channel (45 trials per channel, total N = 270 trials).

---

### 2. Comprehensive Comparative Results Table

| Platform | Channel / Delivery Mode | Total Trials (N) | Exact Message Recoveries | Success Rate (%) | Mean Bit Error Rate (BER) | Channel Preservation Nature | Measurement Methodology |
|:---|:---|:---:|:---:|:---:|:---:|:---|:---:|
| **Discord** | Webhook attachment | 45 | 45 | **100.0%** | 0.00000000 | Byte-preserving | Automated API loop |
| **WhatsApp** | Document mode | 45 | 45 | **100.0%** | 0.00000000 | Byte-preserving file transfer | Empirical trial |
| **Telegram** | sendPhoto | 45 | 36 | **80.0%** | 0.07086806 | Constrained re-compression | Automated Bot API loop |
| **Twitter / X** | Public timeline post | 45 | 0 | **0.0%** | 1.00000000 | Aggressive lossy + dynamic downscaling | Verified delivered download |
| **Instagram** | Public feed post | 45 | 0 | **0.0%** | 1.00000000 | Aggressive lossy + 1080px downsampling | Verified delivered download |
| **WhatsApp** | Standard image | 45 | 0 | **0.0%** | 1.00000000 | Mandatory lossy transcode + downscaling | Empirical trial |
| **Total / Overall** | **All 6 Channels** | **270** | **126** | **46.7%** | — | — | Full Empirical Suite |

---

### 3. Failure Mode & Survivability Mechanics
1. **Byte-Preserving Channels (100% Recovery)**:
   - **Discord Attachment** and **WhatsApp Document Mode** transmit the original JPEG bitstream intact without applying server-side transcoding or spatial resampling.
   - The luminance DCT coefficient arrays and Reed-Solomon codeword structures remain completely unperturbed, yielding BER = 0.00000000.

2. **Dimension-Constrained Channels (80% Recovery)**:
   - **Telegram sendPhoto** re-compresses standard images mildly but generally maintains block dimensions for images under 1280px.
   - However, for high-resolution images (e.g. 3840x2160), Telegram scales the image down to 1280x720, breaking the original 8x8 block grid alignment and causing complete parity decoding failure (BER ~ 0.50).

3. **Lossy & Rescaling Social Feeds (0% Recovery)**:
   - **Twitter/X, Instagram, and WhatsApp Standard Image** perform mandatory server-side transcoding.
   - Spatial downscaling (e.g. downsampling to 1080px or arbitrary mobile viewport dimensions) interpolates adjacent pixels across block boundaries, permanently destroying the original 8x8 DCT grid synchronization.
   - Heavy JPEG quantization tables round the embedded mid-frequency AC coefficient pairs to identical or zero values, preventing synchronization marker ('SHDW') detection.
