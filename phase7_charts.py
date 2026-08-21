"""Phase 7 reporting charts for the ShadowPost platform bench.

Reads phase5_results/platform_trials.csv (produced by phase5_bench.py and
manual_platform_test.py) and renders three summary charts into phase7_results/:

1. success_rate_per_platform.png  - bar chart, % of fully recovered trials
2. average_ber_per_platform.png   - bar chart, mean bit-error rate of delivered images
3. max_capacity_per_cover.png     - bar chart + table, largest embedded payload per cover

Run after platform trials are complete; safe to re-run at any time.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Headless rendering; no display required.
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
TRIAL_CSV = ROOT / "phase5_results" / "platform_trials.csv"
OUT_DIR = ROOT / "phase7_results"


def load_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"missing trial log {path}; run phase5_bench.py or manual_platform_test.py first")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if any((value or "").strip() for value in row.values())]
    if not rows:
        raise SystemExit(f"{path} contains no trial rows")
    return rows


def ordered_platforms(rows: list[dict[str, str]]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        if row["platform"] not in seen:
            seen.append(row["platform"])
    return sorted(seen)


def success_rates(rows: list[dict[str, str]]) -> dict[str, tuple[float, int]]:
    results: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        results[row["platform"]].append(row["success"].strip().lower() == "true")
    return {name: (100.0 * sum(wins) / len(wins), len(wins)) for name, wins in results.items()}


def average_bers(rows: list[dict[str, str]]) -> dict[str, float | None]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        try:
            values[row["platform"]].append(float(row["ber"]))
        except ValueError:  # Empty ber column means structural failure, not measurable damage.
            continue
    averages: dict[str, float | None] = {}
    for name in ordered_platforms(rows):
        scores = values.get(name)
        averages[name] = sum(scores) / len(scores) if scores else None
    return averages


def max_payload_by_cover(rows: list[dict[str, str]]) -> dict[str, tuple[int, int]]:
    best: dict[str, int] = {}
    trials: dict[str, int] = defaultdict(int)
    for row in rows:
        cover = row["cover_name"] or "(unknown)"
        trials[cover] += 1
        try:
            size = int(row["payload_size_bytes"])
        except ValueError:
            continue
        best[cover] = max(best.get(cover, 0), size)
    return {cover: (best.get(cover, 0), count) for cover, count in sorted(trials.items())}


def chart_success_rate(rates: dict[str, tuple[float, int]], destination: Path) -> None:
    names = list(rates)
    values = [rates[name][0] for name in names]
    labels = [f"{rates[name][0]:.0f}%\n(n={rates[name][1]})" for name in names]
    figure, axis = plt.subplots(figsize=(8, 5))
    bars = axis.bar(names, values, color="#4f7cff", edgecolor="white")
    for bar, label in zip(bars, labels):
        axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5, label,
                  ha="center", va="bottom", fontsize=10)
    axis.set_ylim(0, 112)
    axis.set_ylabel("Full-message recovery (%)")
    axis.set_title("ShadowPost: success rate per platform")
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(destination, dpi=150)
    plt.close(figure)


def chart_average_ber(ber_averages: dict[str, float | None], destination: Path) -> None:
    names = list(ber_averages)
    measured = [name for name in names if ber_averages[name] is not None]
    values = [ber_averages[name] for name in measured]
    figure, axis = plt.subplots(figsize=(8, 5))
    bars = axis.bar(measured, values, color="#c2455f", edgecolor="white")
    for bar, name in zip(bars, measured):
        axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{ber_averages[name]:.6f}",
                  ha="center", va="bottom", fontsize=10)
    missing = [name for name in names if ber_averages[name] is None]
    if missing:
        axis.text(0.99, 0.97, "no BER data: " + ", ".join(missing),
                  transform=axis.transAxes, ha="right", va="top", fontsize=9, color="#666666")
    axis.set_ylabel("Mean bit-error rate of delivered image")
    axis.set_title("ShadowPost: average BER per platform")
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(destination, dpi=150)
    plt.close(figure)


def chart_max_capacity(capacities: dict[str, tuple[int, int]], destination: Path) -> None:
    names = list(capacities)
    values = [capacities[name][0] for name in names]
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.barh(names, values, color="#1f7a55", edgecolor="white")
    for index, name in enumerate(names):
        axis.text(values[index], index, f" {values[index]} B", va="center", fontsize=10)
    axis.set_xlabel("Largest payload embedded in trials (bytes)")
    axis.set_title("ShadowPost: max embedded payload per cover")
    axis.invert_yaxis()
    table = axis.table(cellText=[[name, str(capacities[name][1]), f"{capacities[name][0]} B"] for name in names],
                       colLabels=["cover image", "trials", "max payload"], loc="bottom", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)
    axis.set_xticks([])
    figure.subplots_adjust(left=0.22, bottom=0.32)
    figure.savefig(destination, dpi=150, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    rows = load_rows(TRIAL_CSV)
    outputs = {
        "success_rate_per_platform.png": lambda path: chart_success_rate(success_rates(rows), path),
        "average_ber_per_platform.png": lambda path: chart_average_ber(average_bers(rows), path),
        "max_capacity_per_cover.png": lambda path: chart_max_capacity(max_payload_by_cover(rows), path),
    }
    for filename, render in outputs.items():
        destination = OUT_DIR / filename
        render(destination)
        print(f"wrote {destination}")


if __name__ == "__main__":
    main()
