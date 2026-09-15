"""Phase 7 charts for the completed ShadowPost multi-platform trial matrix (N=270)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(r"C:\Users\aakaa\ShadowPost")
TRIAL_CSV = ROOT / "phase5_results" / "platform_trials.csv"
OUT_DIR = ROOT / "phase7_results"
PLATFORM_ORDER = (
    "discord",
    "whatsapp_document",
    "telegram",
    "twitter",
    "instagram",
    "whatsapp_image",
)
PAYLOAD_ORDER = ("small (10 B)", "medium (100 B)", "large (near max)")
COLORS = {
    "discord": "#5865f2",
    "whatsapp_document": "#25d366",
    "telegram": "#0088cc",
    "twitter": "#1da1f2",
    "instagram": "#e1306c",
    "whatsapp_image": "#128c7e",
}
PLATFORM_LABELS = {
    "discord": "Discord\n(Webhook)",
    "whatsapp_document": "WhatsApp\n(Document)",
    "telegram": "Telegram\n(sendPhoto)",
    "twitter": "Twitter / X\n(Post)",
    "instagram": "Instagram\n(Post)",
    "whatsapp_image": "WhatsApp\n(Image)",
}


def load_trials() -> pd.DataFrame:
    if not TRIAL_CSV.is_file():
        raise SystemExit(f"missing trial log: {TRIAL_CSV}")
    frame = pd.read_csv(TRIAL_CSV)
    required = {"platform", "cover_name", "payload_size_bytes", "success"}
    if missing := required - set(frame.columns):
        raise SystemExit(f"trial log missing required columns: {', '.join(sorted(missing))}")
    frame["success"] = frame["success"].astype(str).str.lower().eq("true")
    frame["payload_size_bytes"] = pd.to_numeric(frame["payload_size_bytes"], errors="coerce")
    frame["payload_class"] = pd.Series("large (near max)", index=frame.index)
    frame.loc[frame["payload_size_bytes"].eq(10), "payload_class"] = "small (10 B)"
    frame.loc[frame["payload_size_bytes"].eq(100), "payload_class"] = "medium (100 B)"
    return frame


def annotate_bars(axis: plt.Axes, bars) -> None:
    for bar in bars:
        value = bar.get_height()
        axis.text(bar.get_x() + bar.get_width() / 2, value + 1.5, f"{value:.1f}%",
                  ha="center", va="bottom", fontsize=9, fontweight="bold")


def chart_platform_success(frame: pd.DataFrame) -> pd.DataFrame:
    summary = frame.groupby("platform", sort=False)["success"].agg(["mean", "count"]).reindex(PLATFORM_ORDER)
    values = summary["mean"].mul(100)
    figure, axis = plt.subplots(figsize=(10, 5.5))
    labels = [PLATFORM_LABELS[name] for name in values.index]
    bars = axis.bar(labels, values, color=[COLORS[name] for name in values.index], edgecolor="white", width=0.6)
    annotate_bars(axis, bars)
    axis.set_ylim(0, 115)
    axis.set_ylabel("Full-message recovery (%)", fontsize=11, fontweight="bold")
    axis.set_title("ShadowPost success rate per platform (N=270)", fontsize=13, fontweight="bold", pad=12)
    axis.grid(axis="y", alpha=.25, linestyle="--")
    for label, bar in zip(summary["count"], bars):
        axis.text(bar.get_x() + bar.get_width() / 2, 3.5, f"n={label}", ha="center", color="white", fontweight="bold")
    figure.tight_layout()
    figure.savefig(OUT_DIR / "success_rate_per_platform.png", dpi=150)
    figure.savefig(OUT_DIR / "multi_platform_success_benchmark.png", dpi=150)
    plt.close(figure)
    return summary


def chart_payload_success(frame: pd.DataFrame) -> pd.DataFrame:
    summary = frame.groupby(["payload_class", "platform"], sort=False)["success"].mean().unstack(fill_value=0.0).reindex(
        index=list(PAYLOAD_ORDER), columns=list(PLATFORM_ORDER)
    ).mul(100)
    figure, axis = plt.subplots(figsize=(10, 5.5))
    bar_width = 0.13
    indices = range(len(PAYLOAD_ORDER))
    for idx, platform in enumerate(PLATFORM_ORDER):
        positions = [p + (idx - 2.5) * bar_width for p in indices]
        axis.bar(positions, summary[platform], width=bar_width, label=PLATFORM_LABELS[platform].replace("\n", " "),
                 color=COLORS[platform], edgecolor="white")
    axis.set_xticks(list(indices))
    axis.set_xticklabels(list(PAYLOAD_ORDER), fontweight="bold")
    axis.set_ylim(0, 115)
    axis.set_ylabel("Full-message recovery (%)", fontsize=11, fontweight="bold")
    axis.set_title("ShadowPost success by payload class across all platforms", fontsize=13, fontweight="bold", pad=12)
    axis.grid(axis="y", alpha=.25, linestyle="--")
    axis.legend(loc="upper right", fontsize=9)
    figure.tight_layout()
    figure.savefig(OUT_DIR / "success_rate_by_payload_size.png", dpi=150)
    plt.close(figure)
    return summary


def chart_cover_success(frame: pd.DataFrame) -> None:
    frame["cover_short"] = frame["cover_name"].apply(lambda p: Path(p).parent.name if Path(p).parent.name else Path(p).name)
    summary = frame.groupby("cover_short")["success"].agg(["mean", "count"]).sort_values("mean", ascending=False)
    figure, axis = plt.subplots(figsize=(12, 6))
    bars = axis.bar(summary.index, summary["mean"].mul(100), color="#4f46e5", edgecolor="white", width=0.6)
    annotate_bars(axis, bars)
    axis.set_ylim(0, 115)
    axis.set_ylabel("Full-message recovery (%)", fontsize=11, fontweight="bold")
    axis.set_title("ShadowPost success rate per cover image (across all 270 trials)", fontsize=13, fontweight="bold", pad=12)
    axis.grid(axis="y", alpha=.25, linestyle="--")
    plt.xticks(rotation=45, ha="right", fontsize=10)
    figure.tight_layout()
    figure.savefig(OUT_DIR / "success_rate_per_cover.png", dpi=150)
    plt.close(figure)


def chart_overall_summary(frame: pd.DataFrame) -> tuple[int, int]:
    successes = int(frame["success"].sum())
    failures = len(frame) - successes
    figure, axis = plt.subplots(figsize=(6.5, 6))
    axis.pie([successes, failures], labels=[f"Recovered\n{successes} ({100*successes/len(frame):.1f}%)", f"Failed\n{failures} ({100*failures/len(frame):.1f}%)"],
             colors=["#059669", "#dc2626"], autopct="%.1f%%", startangle=90,
             textprops={"fontsize": 11, "fontweight": "bold"}, wedgeprops={"edgecolor": "white", "linewidth": 2})
    axis.set_title("ShadowPost overall 270-trial benchmark outcome", fontsize=12, fontweight="bold")
    figure.tight_layout()
    figure.savefig(OUT_DIR / "overall_trial_summary.png", dpi=150)
    plt.close(figure)
    return successes, failures


def write_summary(frame: pd.DataFrame, platform_summary: pd.DataFrame, payload_summary: pd.DataFrame,
                  successes: int, failures: int) -> None:
    lines = [
        "ShadowPost Phase 7 Multi-Platform Benchmark Summary",
        f"Total Trials (N): {len(frame)}",
        f"Recovered Exactly: {successes} ({100 * successes / len(frame):.1f}%)",
        f"Failed: {failures} ({100 * failures / len(frame):.1f}%)",
        "",
        "Success rate per platform:",
    ]
    for platform, row in platform_summary.iterrows():
        name = PLATFORM_LABELS[platform].replace("\n", " ")
        lines.append(f"- {name:25s}: {int(round(row['mean'] * row['count']))}/{int(row['count'])} ({row['mean'] * 100:.1f}%)")
    lines.append("")
    lines.append("Success rate by payload class:")
    for payload, row in payload_summary.iterrows():
        rates = ", ".join(f"{p} {rate:.1f}%" for p, rate in row.items())
        lines.append(f"- {payload}: {rates}")
    (OUT_DIR / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    trials = load_trials()
    platform_summary = chart_platform_success(trials)
    payload_summary = chart_payload_success(trials)
    chart_cover_success(trials)
    successes, failures = chart_overall_summary(trials)
    write_summary(trials, platform_summary, payload_summary, successes, failures)
    for path in sorted(OUT_DIR.glob("*.png")):
        print(f"wrote {path}")
    print(f"wrote {OUT_DIR / 'summary.txt'}")


if __name__ == "__main__":
    main()
