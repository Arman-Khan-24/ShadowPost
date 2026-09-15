# ShadowPost - Current State

## Complete: Phases 1-7

- Native JPEG DCT embedding uses jpeglib.read_dct() and write_dct() only.
- Final luminance embedding pairs are positions 0 and 2:
  (1,3) vs (2,2) and (1,4) vs (4,1).
- Extraction tie rule: |A| >= |B| decodes as bit 1.
- Reed-Solomon is fixed at RS(48,32): 32 data bytes and 16 parity bytes.
- AES-256-GCM encrypts each entire message once using a scrypt-derived 32-byte
  key. The container is [2-byte length][12-byte nonce][ciphertext][16-byte tag],
  then split into 32-byte RS data chunks.
- pp.py exposes POST /encode and POST /decode. Capacity is image-specific;
  TestClient round-trip and over-capacity checks pass.
- rontend.html is the completed Phase 6 single-file browser UI.

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
1. **Byte-Preserving Channels (Discord Webhooks, WhatsApp Document)**: Deliver stego JPEGs bit-for-bit without server-side recompression or downsampling. Recovery rate is 100.0%.
2. **Dimension-Constrained Channels (Telegram sendPhoto)**: Telegram allows payload recovery up to 80.0%, but downscales larger images (e.g., 3840x2160 Corsair downscaled to 1280x720), breaking the original 8x8 DCT block grid alignment.
3. **Aggressive Feed Channels (Twitter/X, Instagram, WhatsApp Image)**: All feed-based posts undergo compulsory re-compression and dimensional scaling. This alters or zeros out mid-frequency AC coefficient pairs and desynchronizes the  \times 8$ DCT block boundaries, resulting in 0% recovery and BER = 1.0.

## Phase 7 Reporting & Visualizations

phase7_results/ summarizes the benchmark results:
- 126/270 exact message recoveries across all social media and messaging channels (46.7% overall across all 6 tested delivery pipelines; 93.3% across channels supporting document/unscaled transmission).
- Platform-specific CSVs are organized in phase5_results/:
  - 	elegram_trials.csv
  - discord_trials.csv
  - 	witter_trials.csv
  - instagram_trials.csv
  - whatsapp_image_trials.csv
  - whatsapp_document_trials.csv
  - platform_trials.csv (canonical 270-row master dataset)

## Key Artifacts

- phase1_native_dct_experiment.py - finalized DCT embedding/extraction.
- phase1_results_positions_0_2_tie_fixed/phase1_trials.csv - final Phase 1 cover manifest.
- phase2_rs_roundtrip.py and phase2_rs_results/ - RS(48,32) validation.
- phase3_aes_gcm_roundtrip.py and phase3_aes_gcm_results/ - AES-256-GCM validation.
- pp.py, 	est_app.py, and rontend.html - Phase 4 API and Phase 6 UI.
- phase5_bench.py and phase5_results/platform_trials.csv - delivery bench.
- phase7_charts.py and phase7_results/ - reports and charts.
