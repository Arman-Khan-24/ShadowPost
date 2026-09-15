# ShadowPost: Multi-Platform Survivability Study

## Experimental Design

The benchmark evaluates native-JPEG DCT steganography with Reed-Solomon
RS(48,32) error correction and AES-256-GCM encryption across six delivery modes.
The structured cohort uses 15 covers and three payload classes for Telegram,
Discord, and WhatsApp Document. The feed/media cohort contains 45 fixed
100-byte trials for Twitter/X, Instagram, and WhatsApp Image. The complete
master dataset contains 270 trials.

## Results

| Platform | Delivery mode | Trials | Exact recoveries | Success rate | Mean recorded BER |
|---|---|---:|---:|---:|---:|
| Discord | Webhook attachment | 45 | 45 | 100.0% | 0.00000000 |
| WhatsApp | Document | 45 | 45 | 100.0% | 0.00000000 |
| Telegram | `sendPhoto` | 45 | 36 | 80.0% | 0.02743540 |
| Twitter / X | Public image post | 45 | 0 | 0.0% | 1.00000000 |
| Instagram | Public feed post | 45 | 0 | 0.0% | 1.00000000 |
| WhatsApp | Standard image | 45 | 0 | 0.0% | 1.00000000 |
| **Overall** | **All six modes** | **270** | **126** | **46.7%** | **0.51727204** |

Mean BER is calculated from rows with a recorded BER; capacity-rejected trials
are excluded from that calculation.

## Observed Delivery Behavior

1. Discord attachments and WhatsApp documents preserved the original JPEG
   structure and recovered all tested messages.
2. Telegram recovered most payloads but downscaled selected images, causing DCT
   block-grid registration failures for affected covers.
3. Twitter/X, Instagram, and standard WhatsApp image delivery applied lossy
   transcoding and spatial scaling. The resulting DCT structure did not preserve
   the embedded coefficient relationships, so no exact messages were recovered.

## Reproducibility Artifacts

- `platform_trials.csv` is the canonical master dataset.
- The six `*_trials.csv` files provide platform-specific rows.
- `phase7_charts.py` generates benchmark charts in `phase7_results/`.
- Downloaded Twitter and Instagram media are under `downloaded/`.
