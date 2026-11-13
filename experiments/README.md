# Running experiments

Install `requirements-dev.txt` and the editable package, then run these commands from the repository root. Supply an existing directory containing the source JPEG covers.

```bash
python -m experiments.dct_coefficient_experiment --covers-dir /path/to/covers
python -m experiments.rs_roundtrip --covers-dir /path/to/covers
python -m experiments.aes_gcm_roundtrip --covers-dir /path/to/covers
```

Defaults select 15 covers, Pillow qualities 95/90/80/70/60/50, and the existing lab gap of 24. Use `--output-dir` for a fresh run directory; these scripts refuse to overwrite existing outputs. They report observed recovery failures rather than turning recompression failure into a Python crash.

Inspect saved refined-run ties:

```bash
python -m experiments.inspect_beach_ties
python -m experiments.analyze_dct_failures --results-dir results/phase1 \
  --covers-dir /path/to/original/covers
```

## Manual platform delivery

Each trial should use its own results directory. `--platform` labels the delivery mode and selects its corresponding known profile (`whatsapp_document` maps to `whatsapp_doc`). Unknown labels use the default profile, matching the API behavior.

```bash
python -m experiments.manual_platform_test --results-dir results/local/telegram_trial1 prepare \
  --platform telegram --cover /path/to/cover.jpg \
  --message "Delivery test" --passphrase "your-test-passphrase"
```

Upload the prepared JPEG from that directory's `manual_upload/` folder to the intended platform, then download the delivered image. Check the downloaded file:

```bash
python -m experiments.manual_platform_test --results-dir results/local/telegram_trial1 check \
  --platform telegram --downloaded-image /path/to/downloaded.jpg \
  --passphrase "your-test-passphrase"
```

The helper records dimensions, bit errors when extractable, and decode outcome. It does not persist the passphrase or plaintext. Test passphrases supplied through command-line flags can appear in shell history; do not use personal credentials.

## Automatic delivery benchmark

The existing live benchmark covers **Telegram and Discord only**. It requires the original 15 covers from the refined phase-1 manifest. The other platforms use manual upload/download checks.

```bash
python -m experiments.platform_benchmark --covers-dir /path/to/original/covers
```

Live mode reads `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `DISCORD_WEBHOOK_URL` from the environment or ignored root `.env`; it uploads images to those destinations. Output defaults to `results/local/platform_trials.csv`, with an overwrite guard.

For local code verification without network uploads:

```bash
python -m experiments.platform_benchmark --offline --covers-dir /path/to/original/covers
```

Offline rows are labeled `offline_loopback`: these validate imports and local round trips, and are not platform survivability measurements.

## Reporting scripts

```bash
python -m scripts.benchmark_charts
python -m scripts.generate_paper_figures
python -m scripts.offline_paper_analysis --covers-dir /path/to/original/covers
python -m scripts.make_ieee_paper
```

Reporting scripts default to `results/local/`, reading the preserved study. The supplementary analysis requires the original cover images; archived JPEG stego files alone cannot replace them.
