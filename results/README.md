# Recorded research results

These files preserve the August–September 2026 study. They are research evidence and have not been replaced by newer manual checks. For latest delivery status, see [the main README](../README.md#platform-test-results).

## Canonical delivery study

Source: [phase5/platform_trials.csv](phase5/platform_trials.csv), **270 rows**, dated 22 August and 15 September 2026. Counts below are computed from the `success` field, not inferred from platform descriptions.

| Platform | Delivery mode | Samples | Pass | Fail | Exact recovery rate |
|---|---|---:|---:|---:|---:|
| Discord | Attachment | 45 | 45 | 0 | 100% |
| WhatsApp | Document | 45 | 45 | 0 | 100% |
| Telegram | Image | 45 | 36 | 9 | 80% |
| WhatsApp | Image | 45 | 0 | 45 | 0% |
| Twitter / X | Image | 45 | 0 | 45 | 0% |
| Instagram | Image | 45 | 0 | 45 | 0% |
| **Total** | **Six delivery modes** | **270** | **126** | **144** | **126/270** |

Telegram, Discord, and WhatsApp Document use the 15-cover, three-payload matrix. Twitter/X, Instagram, and WhatsApp Image contain 45 fixed 100-byte trials per mode. Failure counts include capacity-rejected trials. Some historical rows originated in manual reports and lack delivered-image measurements; they must not all be described as automated telemetry. BER values of `1.0` attached to extraction failures do not establish a measured transform or full bit-by-bit comparison.

The newer manual retests reported by the author on 13 November 2026 recovered messages on five modes; WhatsApp Image still failed. Those retests have no saved per-trial log or count, so the numerical table above describes only the preserved study.

## Folder map

- `phase1/`: original coefficient-pair experiment.
- `phase1_positions_0_2/`: pair-subset experiment.
- `phase1_positions_0_2_tie_fixed/`: refined deterministic-tie run.
- `phase2_rs/`: RS(48,32) experiment.
- `phase3_aes_gcm/`: fixed-container AES-GCM experiment and negative checks.
- `phase5/`: delivery records and artifacts.
- `phase7/`: benchmark charts and summary.
- `offline_analysis/`: supplementary controlled-transform and detectability analysis.
- `downloaded/`: retained delivered platform media.
- `local/`: ignored new-run outputs; not part of the recorded study.

All historical result images, CSV rows, configs, and numerical summaries were retained during cleanup. Original Windows paths inside recorded configs are preserved as provenance. Source cover images are external to the repo.
