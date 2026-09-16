"""Generate publication figures from the canonical ShadowPost trial CSV."""
from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "phase5_results" / "platform_trials.csv"
OUT_DIR = ROOT / "paper_figures"

ORDER = ["discord", "whatsapp_document", "telegram", "twitter", "instagram", "whatsapp_image"]
LABELS = {
    "discord": "Discord",
    "whatsapp_document": "WA Doc",
    "telegram": "Telegram",
    "twitter": "X",
    "instagram": "Instagram",
    "whatsapp_image": "WA Image",
}
FAILURES = [
    "fixed_grid_extraction_failed",
    "reed_solomon_decode_failed",
    "capacity_failure",
    "authentication_failed",
]


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    p = successes / trials
    d = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / d
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / d
    return centre - margin, centre + margin


def configure() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "TeX Gyre Termes", "DejaVu Serif"],
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 9,
        "legend.fontsize": 6.5,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.linewidth": 0.7,
    })


def save(fig: plt.Figure, name: str) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT_DIR / f"{name}.eps", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT_DIR / f"{name}.png", dpi=220, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def figure1(rows: list[dict[str, str]]) -> None:
    counts = Counter(row["platform"] for row in rows)
    successes = Counter(row["platform"] for row in rows if row["success"].lower() == "true")
    rates, low, high = [], [], []
    for platform in ORDER:
        rate = successes[platform] / counts[platform]
        lo, hi = wilson(successes[platform], counts[platform])
        rates.append(rate * 100)
        low.append((rate - lo) * 100)
        high.append((hi - rate) * 100)
    colors = ["#009E73", "#009E73", "#E69F00", "#D55E00", "#D55E00", "#D55E00"]
    hatches = ["", "", "//", "xx", "xx", "xx"]
    fig, ax = plt.subplots(figsize=(3.45, 2.45))
    bars = ax.bar(range(6), rates, color=colors, edgecolor="black", linewidth=0.65,
                  yerr=np.array([low, high]), capsize=2.5, error_kw={"elinewidth": 0.8, "capthick": 0.8})
    for bar, hatch, ok, n in zip(bars, hatches, [successes[p] for p in ORDER], [counts[p] for p in ORDER]):
        bar.set_hatch(hatch)
        ax.text(bar.get_x() + bar.get_width()/2, max(bar.get_height() + 4, 3), f"{ok}/{n}", ha="center", va="bottom", fontsize=6.5)
    ax.set_xticks(range(6), [LABELS[p] for p in ORDER], rotation=28, ha="right")
    ax.set_ylabel("Exact recovery rate (%)")
    ax.set_ylim(0, 114)
    ax.set_yticks(range(0, 101, 20))
    ax.grid(axis="y", linestyle=":", linewidth=0.55, color="0.55")
    ax.set_axisbelow(True)
    save(fig, "fig1_recovery_ci")


def payload_class(row: dict[str, str]) -> str:
    size = int(row["payload_size_bytes"])
    if size == 10:
        return "10 B"
    if size == 100:
        return "100 B"
    return "Near-capacity"


def figure2(rows: list[dict[str, str]]) -> None:
    classes = ["10 B", "100 B", "Near-capacity"]
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["platform"], payload_class(row))].append(row)
    matrix = np.full((6, 3), np.nan)
    annotations: list[list[str]] = [["N/A"] * 3 for _ in range(6)]
    for i, platform in enumerate(ORDER):
        for j, cls in enumerate(classes):
            group = grouped.get((platform, cls), [])
            if group:
                ok = sum(row["success"].lower() == "true" for row in group)
                matrix[i, j] = 100 * ok / len(group)
                annotations[i][j] = f"{ok}/{len(group)}"
    fig, ax = plt.subplots(figsize=(3.45, 2.65))
    cmap = matplotlib.colormaps["cividis"].copy()
    cmap.set_bad("#E6E6E6")
    image = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=100, aspect="auto")
    for i in range(6):
        for j in range(3):
            if np.isnan(matrix[i, j]):
                ax.add_patch(plt.Rectangle((j-.5, i-.5), 1, 1, fill=False, hatch="///", edgecolor="0.35", linewidth=0.6))
                color = "black"
            else:
                color = "white" if matrix[i, j] < 35 or matrix[i, j] > 75 else "black"
            ax.text(j, i, annotations[i][j], ha="center", va="center", color=color, fontweight="bold", fontsize=7)
    ax.set_xticks(range(3), classes)
    ax.set_yticks(range(6), [LABELS[p] for p in ORDER])
    ax.set_xlabel("Payload class")
    ax.set_ylabel("Delivery mode")
    ax.set_xticks(np.arange(-.5, 3, 1), minor=True)
    ax.set_yticks(np.arange(-.5, 6, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)
    cbar = fig.colorbar(image, ax=ax, fraction=0.05, pad=0.04)
    cbar.set_label("Exact recovery rate (%)")
    save(fig, "fig2_payload_heatmap")


def figure3(rows: list[dict[str, str]]) -> None:
    categories = ["success"] + FAILURES
    labels = ["Success", "Fixed-grid extraction", "RS decode", "Capacity", "Authentication"]
    colors = ["#009E73", "#0072B2", "#CC79A7", "#E69F00", "#D55E00"]
    hatches = ["", "xx", "..", "//", "++"]
    values = np.zeros((6, 5))
    raw = np.zeros((6, 5), dtype=int)
    for i, platform in enumerate(ORDER):
        group = [row for row in rows if row["platform"] == platform]
        for row in group:
            category = "success" if row["success"].lower() == "true" else row["failure_reason"]
            if category in categories:
                raw[i, categories.index(category)] += 1
        values[i] = raw[i] / len(group) * 100
    fig, ax = plt.subplots(figsize=(3.45, 2.65))
    left = np.zeros(6)
    for j, (label, color, hatch) in enumerate(zip(labels, colors, hatches)):
        bars = ax.barh(range(6), values[:, j], left=left, label=label, color=color, edgecolor="black", linewidth=0.45, hatch=hatch)
        for i, bar in enumerate(bars):
            if raw[i, j] >= 2:
                ax.text(left[i] + values[i, j]/2, i, str(raw[i, j]), ha="center", va="center", fontsize=6.5,
                        color="white" if color in {"#0072B2", "#D55E00"} else "black")
        left += values[:, j]
    ax.set_yticks(range(6), [LABELS[p] for p in ORDER])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Proportion of trials (%)")
    ax.grid(axis="x", linestyle=":", linewidth=0.55, color="0.55")
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.23), ncol=2, frameon=False)
    save(fig, "fig3_failure_taxonomy")


def figure4() -> None:
    fig, ax = plt.subplots(figsize=(7.1, 2.05))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3)
    ax.axis("off")
    boxes = [
        (0.05, 1.72, "Plaintext"), (1.25, 1.72, "scrypt key\nderivation"),
        (2.65, 1.72, "AES-256-GCM\nencryption"), (4.15, 1.72, "Framing\n$L\\,||\\,N\\,||\\,C\\,||\\,T$"),
        (5.65, 1.72, "RS(48,32)\nencoding"), (7.05, 1.72, "DCT coefficient-\npair embedding"),
        (8.75, 1.72, "Delivery / platform\ntransform"),
        (8.75, 0.35, "Extraction"), (7.05, 0.35, "RS decoding"),
        (5.55, 0.35, "AES-GCM\nauthentication"), (3.9, 0.35, "Plaintext\nor Reject"),
    ]
    sizes = [1.0, 1.15, 1.25, 1.25, 1.15, 1.4, 1.5, 1.15, 1.15, 1.25, 1.15]
    for (x, y, text), width in zip(boxes, sizes):
        uncertain = "Delivery" in text
        patch = FancyBboxPatch((x, y), width, 0.75, boxstyle="round,pad=0.03",
                               facecolor="0.86" if uncertain else "white", edgecolor="black",
                               linewidth=1.4 if uncertain else 0.8, linestyle="--" if uncertain else "-")
        ax.add_patch(patch)
        ax.text(x + width/2, y + .375, text, ha="center", va="center", fontsize=7)
    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "black"})
    top = [(1.05,2.095,1.25,2.095),(2.4,2.095,2.65,2.095),(3.9,2.095,4.15,2.095),(5.4,2.095,5.65,2.095),(6.8,2.095,7.05,2.095),(8.45,2.095,8.75,2.095)]
    for coords in top: arrow(*coords)
    arrow(9.5,1.72,9.5,1.10); arrow(9.5,1.10,9.325,1.10); arrow(9.325,1.10,9.325,0.35)
    arrow(8.75,0.725,8.2,0.725); arrow(7.05,0.725,6.8,0.725); arrow(5.55,0.725,5.05,0.725)
    ax.text(9.5, 1.35, "uncertainty / failure injection", ha="center", va="center", fontsize=6.5, fontweight="bold")
    save(fig, "fig4_system_pipeline")


def write_summary(rows: list[dict[str, str]]) -> None:
    counts = Counter(row["platform"] for row in rows)
    successes = Counter(row["platform"] for row in rows if row["success"].lower() == "true")
    failures = Counter((row["platform"], row["failure_reason"]) for row in rows if row["success"].lower() != "true")
    lines = ["Generated from phase5_results/platform_trials.csv", ""]
    for platform in ORDER:
        lo, hi = wilson(successes[platform], counts[platform])
        lines.append(f"{platform}: {successes[platform]}/{counts[platform]}, Wilson 95% CI {100*lo:.1f}-{100*hi:.1f}%")
        for reason in FAILURES:
            lines.append(f"  {reason}: {failures[(platform, reason)]}")
    (OUT_DIR / "figure_data_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_latex_tables(rows: list[dict[str, str]]) -> None:
    counts = Counter(row["platform"] for row in rows)
    successes = Counter(row["platform"] for row in rows if row["success"].lower() == "true")
    bers: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row["ber"]:
            bers[row["platform"]].append(float(row["ber"]))
    result_rows = []
    for platform in ORDER:
        n, ok = counts[platform], successes[platform]
        lo, hi = wilson(ok, n)
        mean_ber = sum(bers[platform]) / len(bers[platform]) if bers[platform] else 0.0
        result_rows.append(
            f"{LABELS[platform]} & {n} & {ok} & {100*ok/n:.1f}\\% & "
            f"{100*lo:.1f}--{100*hi:.1f}\\% & {mean_ber:.4f} \\\\"
        )
    all_ber = [float(row["ber"]) for row in rows if row["ber"]]
    total_ok = sum(successes.values())
    lo, hi = wilson(total_ok, len(rows))
    result_rows.append("\\midrule")
    result_rows.append(
        f"Overall & {len(rows)} & {total_ok} & {100*total_ok/len(rows):.1f}\\% & "
        f"{100*lo:.1f}--{100*hi:.1f}\\% & {sum(all_ber)/len(all_ber):.4f} \\\\"
    )
    terminal = {
        "discord": "success",
        "whatsapp_document": "success",
        "telegram": "capacity / RS decode",
        "twitter": "fixed-grid extraction",
        "instagram": "fixed-grid extraction",
        "whatsapp_image": "fixed-grid extraction",
    }
    cohorts = {p: ("15 x 3" if p in {"discord", "whatsapp_document", "telegram"} else "45 x 100 B") for p in ORDER}
    comparison_rows = [
        f"{LABELS[p]} & {cohorts[p]} & {successes[p]}/{counts[p]} & {terminal[p]} \\\\"
        for p in ORDER
    ]
    content = (
        "% Generated by generate_paper_figures.py from phase5_results/platform_trials.csv.\n"
        "\\newcommand{\\ResultTableRows}{%\n" + "\n".join(result_rows) + "\n}\n"
        "\\newcommand{\\ComparisonTableRows}{%\n" + "\n".join(comparison_rows) + "\n}\n"
    )
    (OUT_DIR / "generated_results.tex").write_text(content, encoding="utf-8")


def main() -> None:
    configure()
    rows = load_rows()
    figure1(rows)
    figure2(rows)
    figure3(rows)
    figure4()
    write_summary(rows)
    write_latex_tables(rows)
    print(f"generated figures in {OUT_DIR}")


if __name__ == "__main__":
    main()
