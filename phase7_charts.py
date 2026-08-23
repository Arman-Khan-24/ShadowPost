"""Phase 7 charts for the completed ShadowPost platform trial matrix."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
TRIAL_CSV = ROOT / "phase5_results" / "platform_trials.csv"
OUT_DIR = ROOT / "phase7_results"
PLATFORM_ORDER = ("telegram", "discord")
PAYLOAD_ORDER = ("small (10 B)", "medium (100 B)", "large (near max)")
COLORS = {"telegram": "#4f7cff", "discord": "#5865f2"}


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
        axis.text(bar.get_x() + bar.get_width() / 2, value + 1.5, f"{value:.0f}%",
                  ha="center", va="bottom", fontsize=9, fontweight="bold")


def chart_platform_success(frame: pd.DataFrame) -> pd.DataFrame:
    summary = frame.groupby("platform", sort=False)["success"].agg(["mean", "count"]).reindex(PLATFORM_ORDER)
    values = summary["mean"].mul(100)
    figure, axis = plt.subplots(figsize=(7, 5))
    bars = axis.bar(values.index.str.title(), values, color=[COLORS[name] for name in values.index], edgecolor="white")
    annotate_bars(axis, bars)
    axis.set_ylim(0, 112)
    axis.set_ylabel("Full-message recovery (%)")
    axis.set_title("ShadowPost success rate per platform")
    axis.grid(axis="y", alpha=.25)
    for label, bar in zip(summary["count"], bars):
        axis.text(bar.get_x() + bar.get_width() / 2, 4, f"n={label}", ha="center", color="white", fontweight="bold")
    figure.tight_layout()
    figure.savefig(OUT_DIR / "success_rate_per_platform.png", dpi=150)
    plt.close(figure)
    return summary


def chart_payload_success(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = (frame.groupby(["payload_class", "platform"])["success"].mean().mul(100).unstack("platform")
               .reindex(index=PAYLOAD_ORDER, columns=PLATFORM_ORDER))
    figure, axis = plt.subplots(figsize=(9, 5.5))
    grouped.plot(kind="bar", ax=axis, color=[COLORS[name] for name in grouped.columns], edgecolor="white", width=.72)
    for container in axis.containers:
        annotate_bars(axis, container)
    axis.set_ylim(0, 112)
    axis.set_xlabel("Payload size")
    axis.set_ylabel("Full-message recovery (%)")
    axis.set_title("ShadowPost success rate by payload size")
    axis.legend(title="Platform", labels=[name.title() for name in grouped.columns])
    axis.grid(axis="y", alpha=.25)
    figure.tight_layout()
    figure.savefig(OUT_DIR / "success_rate_by_payload_size.png", dpi=150)
    plt.close(figure)
    return grouped


def chart_cover_success(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby("cover_name", sort=False)["success"].agg(["mean", "count"])
    values = grouped["mean"].mul(100).sort_values(ascending=True)
    figure, axis = plt.subplots(figsize=(10, 7))
    bars = axis.barh(values.index, values, color="#059669", edgecolor="white")
    for bar in bars:
        axis.text(min(bar.get_width() + 1, 101), bar.get_y() + bar.get_height() / 2, f"{bar.get_width():.0f}%",
                  va="center", fontsize=8)
    axis.set_xlim(0, 112)
    axis.set_xlabel("Full-message recovery (%) across Telegram and Discord")
    axis.set_title("ShadowPost success rate per cover image")
    axis.grid(axis="x", alpha=.25)
    figure.tight_layout()
    figure.savefig(OUT_DIR / "success_rate_per_cover.png", dpi=150)
    plt.close(figure)
    return grouped


def chart_overall_summary(frame: pd.DataFrame) -> tuple[int, int]:
    successes = int(frame["success"].sum())
    failures = int(len(frame) - successes)
    figure, axis = plt.subplots(figsize=(7, 5.5))
    axis.pie([successes, failures], labels=[f"Recovered\n{successes}", f"Failed\n{failures}"],
             colors=["#059669", "#dc2626"], autopct="%.1f%%", startangle=90,
             textprops={"fontsize": 11}, wedgeprops={"edgecolor": "white", "linewidth": 2})
    axis.set_title("ShadowPost overall 90-trial outcome")
    figure.tight_layout()
    figure.savefig(OUT_DIR / "overall_trial_summary.png", dpi=150)
    plt.close(figure)
    return successes, failures


def write_summary(frame: pd.DataFrame, platform_summary: pd.DataFrame, payload_summary: pd.DataFrame,
                  successes: int, failures: int) -> None:
    lines = [
        "ShadowPost Phase 7 summary",
        f"Trials: {len(frame)}",
        f"Recovered exactly: {successes} ({100 * successes / len(frame):.1f}%)",
        f"Failed: {failures} ({100 * failures / len(frame):.1f}%)",
        "",
        "Success rate per platform:",
    ]
    for platform, row in platform_summary.iterrows():
        lines.append(f"- {platform}: {int(row['mean'] * row['count'])}/{int(row['count'])} ({row['mean'] * 100:.1f}%)")
    lines.append("")
    lines.append("Success rate by payload class:")
    for payload, row in payload_summary.iterrows():
        rates = ", ".join(f"{platform} {rate:.1f}%" for platform, rate in row.items())
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
