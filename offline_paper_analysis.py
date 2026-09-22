"""Offline, reproducible supplementary analysis; never contacts a platform."""
from __future__ import annotations

import argparse
import csv
import json
import math
import tempfile
from pathlib import Path

import jpeglib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from cryptography.exceptions import InvalidTag
from reedsolo import RSCodec, ReedSolomonError
from scipy.ndimage import uniform_filter
from scipy.optimize import linear_sum_assignment
from scipy.stats import spearmanr

from phase1_native_dct_experiment import PAIR_POSITIONS, extract_native_dct, luminance_coefficients
from phase2_rs_roundtrip import bits_to_bytes
from phase3_aes_gcm_roundtrip import RS_PARITY_BYTES, decrypt_container, derive_aes256_key

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "offline_analysis"
PLATFORMS = ("discord", "telegram", "whatsapp_document")
PHASE3_PASS = "ShadowPost Phase 3 integration test passphrase"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(name, rows):
    if not rows:
        return
    with (OUT / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def figure(name, fig):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.eps", bbox_inches="tight")
    plt.close(fig)


def pixels(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float64)


def quality(a, b):
    if a.shape != b.shape:
        return None, None
    mse = np.mean((a - b) ** 2)
    psnr = math.inf if mse == 0 else 10 * math.log10(255 ** 2 / mse)
    # Standard local-window SSIM approximation, averaged over RGB channels.
    values = []
    for channel in range(3):
        x, y = a[:, :, channel], b[:, :, channel]
        mx, my = uniform_filter(x, 11), uniform_filter(y, 11)
        vx = uniform_filter(x * x, 11) - mx * mx
        vy = uniform_filter(y * y, 11) - my * my
        cov = uniform_filter(x * y, 11) - mx * my
        score = ((2 * mx * my + (0.01 * 255) ** 2) * (2 * cov + (0.03 * 255) ** 2)) / \
                ((mx ** 2 + my ** 2 + (0.01 * 255) ** 2) * (vx + vy + (0.03 * 255) ** 2))
        values.append(float(np.mean(score)))
    return psnr, float(np.mean(values))


def transform(source, destination, kind):
    with Image.open(source) as original:
        image = original.convert("RGB")
        width, height = image.size
        if kind.startswith("resize"):
            scale = float(kind.split("_")[1])
            image = image.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
        elif kind.startswith("crop"):
            fraction = float(kind.split("_")[1])
            dw, dh = round(width * fraction), round(height * fraction)
            image = image.crop((dw, dh, width - dw, height - dh))
        q = int(kind.split("q")[-1])
        image.save(destination, "JPEG", quality=q, subsampling=0)


def decode_phase3(source):
    bits = extract_native_dct(source, 48 * 8, (0, 2))
    recovered, _, _ = RSCodec(RS_PARITY_BYTES).decode(bits_to_bytes(bits))
    return decrypt_container(derive_aes256_key(PHASE3_PASS), bytes(recovered))


def controlled(covers):
    kinds = ("jpeg_q95", "jpeg_q75", "jpeg_q50", "resize_0.9_q95",
             "resize_0.75_q75", "crop_0.02_q95", "crop_0.05_q75")
    rows, visual = [], []
    bit_count = 48 * 8
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        for index, (cover_name, cover) in enumerate(covers, 1):
            stego = ROOT / "phase3_aes_gcm_results" / f"{index:02d}_{cover.stem}_q95_stego.jpg"
            derivative = work / "transform.jpg"
            expected = decode_phase3(stego)
            source_bits = extract_native_dct(stego, bit_count, (0, 2))
            cover_pixels = pixels(cover)
            stego_pixels = pixels(stego)
            psnr, ssim = quality(cover_pixels, stego_pixels)
            visual.append(dict(cover=cover_name, comparison="cover_to_stego", psnr=psnr, ssim=ssim,
                               source_size=str(cover_pixels.shape[:2]), target_size=str(stego_pixels.shape[:2])))
            for kind in kinds:
                transform(stego, derivative, kind)
                with Image.open(derivative) as image:
                    w, h = image.size
                try:
                    bits = extract_native_dct(derivative, bit_count, (0, 2))
                    ber = float(np.mean(bits != source_bits))
                except ValueError:
                    ber = None
                try:
                    recovered = decode_phase3(derivative)
                    success = recovered == expected
                    reason = "success" if success else "plaintext_mismatch"
                except (ReedSolomonError, InvalidTag, ValueError, UnicodeDecodeError) as exc:
                    success = False
                    reason = type(exc).__name__
                transformed_pixels = pixels(derivative)
                aligned_stego = stego_pixels
                if transformed_pixels.shape != stego_pixels.shape:
                    with Image.open(stego) as image:
                        aligned_stego = np.asarray(image.convert("RGB").resize(
                            (transformed_pixels.shape[1], transformed_pixels.shape[0]), Image.Resampling.LANCZOS), dtype=np.float64)
                p, s = quality(aligned_stego, transformed_pixels)
                rows.append(dict(cover=cover_name, transform=kind, width=w, height=h,
                                 width_ratio=w / stego_pixels.shape[1], height_ratio=h / stego_pixels.shape[0],
                                 success=int(success), ber=ber, decoder_outcome=reason,
                                 aligned_psnr=p, aligned_ssim=s))
            print(f"controlled: {index}/{len(covers)} covers")
    for row in rows:
        row["transform_family"] = "coefficient_noise" if row["transform"].startswith("jpeg") else "geometric_desync"
        row["mechanism"] = "coefficient_noise" if row["transform"].startswith("jpeg") else "geometric_desync"
    write_csv("controlled_transforms.csv", rows)
    summary = []
    for kind in kinds:
        subset = [r for r in rows if r["transform"] == kind]
        bers = [float(r["ber"]) for r in subset if r["ber"] not in (None, "")]
        summary.append({
            "transform": kind,
            "mechanism": subset[0]["mechanism"],
            "n": len(subset),
            "successes": sum(int(r["success"]) for r in subset),
            "recovery_rate": sum(int(r["success"]) for r in subset) / len(subset),
            "mean_ber": float(np.mean(bers)) if bers else "",
            "median_ber": float(np.median(bers)) if bers else "",
            "mean_aligned_psnr": float(np.mean([float(r["aligned_psnr"]) for r in subset])),
            "mean_aligned_ssim": float(np.mean([float(r["aligned_ssim"]) for r in subset])),
        })
    write_csv("controlled_transform_summary.csv", summary)
    write_csv("visual_quality.csv", visual)
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.1, 2.55))
    labels = ["Q95", "Q75", "Q50", "0.90x\nQ95", "0.75x\nQ75", "crop 2%\nQ95", "crop 5%\nQ75"]
    x = np.arange(len(kinds))
    recovery = [row["recovery_rate"] for row in summary]
    mean_ber = [row["mean_ber"] for row in summary]
    colors = ["#777777" if row["mechanism"] == "coefficient_noise" else "#bdbdbd" for row in summary]
    hatches = ["" if row["mechanism"] == "coefficient_noise" else "//" for row in summary]
    bars = ax.bar(x, recovery, color=colors, edgecolor="black", linewidth=.5)
    for bar, hatch, row in zip(bars, hatches, summary):
        bar.set_hatch(hatch)
        ax.text(bar.get_x() + bar.get_width() / 2, max(bar.get_height() + .04, .04),
                f"{row['successes']}/{row['n']}", ha="center", va="bottom", fontsize=6.5)
    ax.set_ylabel("Exact recovery rate")
    ax.set_ylim(0, 1.12)
    ax.set_yticks(np.arange(0, 1.01, .2), [f"{100*v:.0f}" for v in np.arange(0, 1.01, .2)])
    ax.set_ylabel("Recovery rate (%)")
    ax.set_xticks(x, labels)
    ax.grid(axis="y", alpha=.3)
    ax.set_axisbelow(True)
    bx.bar(x, mean_ber, color=colors, edgecolor="black", linewidth=.5, hatch="")
    for index, (bar, hatch) in enumerate(zip(bx.patches, hatches)):
        bar.set_hatch(hatch)
    bx.set_ylabel("Mean aligned BER")
    bx.set_ylim(0, .62)
    bx.set_xticks(x, labels)
    bx.grid(axis="y", alpha=.3)
    bx.set_axisbelow(True)
    fig.suptitle("Controlled offline transforms of retained Phase 3 stego JPEGs", fontsize=9)
    figure("controlled_transform_effects", fig)
    return rows, visual


def fingerprint(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB").resize((24, 24), Image.Resampling.BILINEAR), dtype=np.float64).ravel() / 255


def align_pixels(source, target):
    with Image.open(target) as delivered:
        size = delivered.size
    with Image.open(source) as image:
        aligned = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
        return np.asarray(aligned, dtype=np.float64), pixels(target)


def manual_cover_name(source_name, covers):
    """Resolve retained manual-upload names against the exact cover manifest when possible."""
    stem = Path(source_name).stem
    for cover_name, _ in covers:
        key = Path(cover_name).with_suffix("").as_posix().replace("/", "_")
        if stem.startswith(f"instagram_{key}_"):
            return cover_name
    return ""


def platform_analysis(rows, covers):
    summary = []
    for platform in sorted({r["platform"] for r in rows}):
        group = [r for r in rows if r["platform"] == platform]
        for reason in sorted({r["failure_reason"] or "success" for r in group}):
            subset = [r for r in group if (r["failure_reason"] or "success") == reason]
            valid = [float(r["ber"]) for r in subset if r["ber"]]
            summary.append(dict(platform=platform, outcome=reason, n=len(subset),
                                ber_observed=len(valid), mean_ber=np.mean(valid) if valid else ""))
    write_csv("failure_breakdown.csv", summary)
    dimension = []
    for row in rows:
        rel = row["cover_name"].replace("\\", "/")
        path = ROOT / "downloaded" / rel
        if path.is_file():
            with Image.open(path) as image:
                width, height = image.size
            dimension.append(dict(platform=row["platform"], trial=row["trial"], delivered_file=rel,
                                  delivered_width=width, delivered_height=height,
                                  original_width="", original_height="", width_ratio="", height_ratio="",
                                  note="canonical CSV records delivered dimensions only through file inspection"))
    write_csv("delivered_dimensions_unpaired.csv", dimension)
    # The repository retains exactly 45 upload artifacts and 45 returns for each feed.
    # Pair them by a one-to-one minimum-cost assignment of low-resolution RGB thumbnails.
    sources = sorted((ROOT / "phase5_results" / "manual_upload").glob("*.jpg"))
    source_features = np.stack([fingerprint(path) for path in sources])
    paired = []
    canonical = {
        platform: {Path(row["cover_name"]).name: row for row in rows if row["platform"] == platform}
        for platform in ("instagram", "twitter")
    }
    for platform in ("instagram", "twitter"):
        delivered = sorted((ROOT / "downloaded" / platform).glob("*.jpg"))
        if len(sources) != 45 or len(delivered) != 45:
            continue
        target_features = np.stack([fingerprint(path) for path in delivered])
        costs = np.mean((source_features[:, None, :] - target_features[None, :, :]) ** 2, axis=2)
        src_indices, dst_indices = linear_sum_assignment(costs)
        assigned_costs = costs[src_indices, dst_indices]
        for source_index, target_index in zip(src_indices, dst_indices):
            source, target = sources[source_index], delivered[target_index]
            aligned, returned = align_pixels(source, target)
            psnr, ssim = quality(aligned, returned)
            cover_name = manual_cover_name(source.name, covers)
            cover_psnr, cover_ssim = "", ""
            if cover_name:
                cover_path = dict(covers)[cover_name]
                cover_aligned, _ = align_pixels(cover_path, target)
                cover_psnr, cover_ssim = quality(cover_aligned, returned)
            with Image.open(source) as a, Image.open(target) as b:
                source_size, target_size = a.size, b.size
            trial = canonical[platform].get(target.name, {})
            paired.append(dict(platform=platform, source_file=source.name, delivered_file=target.name,
                               trial=trial.get("trial", ""), cover_name=cover_name,
                               canonical_success=trial.get("success", ""), canonical_ber=trial.get("ber", ""),
                               failure_reason=trial.get("failure_reason", ""),
                               source_width=source_size[0], source_height=source_size[1],
                               delivered_width=target_size[0], delivered_height=target_size[1],
                               width_ratio=target_size[0] / source_size[0], height_ratio=target_size[1] / source_size[1],
                               thumbnail_match_mse=costs[source_index, target_index],
                               match_cost_percentile=float(np.mean(assigned_costs <= costs[source_index, target_index])),
                               stego_to_delivered_psnr=psnr, stego_to_delivered_ssim=ssim,
                               cover_to_delivered_psnr=cover_psnr, cover_to_delivered_ssim=cover_ssim))
    write_csv("delivered_quality_paired.csv", paired)
    dimension_summary = []
    for platform in ("discord", "telegram", "whatsapp_document", "twitter", "instagram", "whatsapp_image"):
        csv_group = [r for r in rows if r["platform"] == platform]
        group = [r for r in paired if r["platform"] == platform]
        ratios = [float(r["width_ratio"]) for r in group]
        ber = [float(r["canonical_ber"]) for r in group if r["canonical_ber"]]
        rho = ""
        if len(set(ratios)) > 1 and len(ber) == len(ratios) and len(set(ber)) > 1:
            rho = float(spearmanr(ratios, ber).statistic)
        dimension_summary.append(dict(
            platform=platform,
            csv_rows=len(csv_group),
            csv_dimension_rows=sum(bool(r["delivered_width"] and r["delivered_height"]) for r in csv_group),
            artifact_paired_rows=len(group),
            mean_width_ratio=float(np.mean(ratios)) if ratios else "",
            min_width_ratio=float(np.min(ratios)) if ratios else "",
            max_width_ratio=float(np.max(ratios)) if ratios else "",
            ber_rows=len(ber),
            spearman_width_ratio_vs_ber=rho,
            note="artifact pairing available" if group else "no row-level delivered dimensions available",
        ))
    write_csv("failure_dimension_analysis.csv", dimension_summary)
    return summary, paired, dimension_summary


def capacity(rows):
    out = []
    for platform in PLATFORMS:
        group = sorted((r for r in rows if r["platform"] == platform), key=lambda r: int(r["trial"]))
        if len(group) != 45:
            raise ValueError(f"{platform} must have 45 structured rows")
        for payload_class, subset in zip(("10 B", "100 B", "near capacity"),
                                         (group[0::3], group[1::3], group[2::3])):
            valid = [float(r["ber"]) for r in subset if r["ber"]]
            out.append(dict(platform=platform, payload_class=payload_class, n=len(subset),
                            successes=sum(r["success"].lower() == "true" for r in subset),
                            min_bytes=min(int(r["payload_size_bytes"]) for r in subset),
                            max_bytes=max(int(r["payload_size_bytes"]) for r in subset),
                            ber_n=len(valid), mean_observed_ber=np.mean(valid) if valid else ""))
    write_csv("capacity_curves.csv", out)
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.15, 2.55), sharex=True)
    styles = (("discord", "o", "-"), ("telegram", "s", "--"), ("whatsapp_document", "^", ":"))
    for platform, marker, line in styles:
        group = [r for r in out if r["platform"] == platform]
        x = np.arange(3)
        ax.plot(x, [r["successes"] / r["n"] for r in group], marker=marker, linestyle=line, color="black", label=platform.replace("_", " "))
        bx.plot(x, [float(r["mean_observed_ber"]) for r in group], marker=marker, linestyle=line, color="black")
    for axis in (ax, bx):
        axis.set_xticks(range(3), ("10 B", "100 B", "near capacity"))
        axis.grid(alpha=.25)
    ax.set_ylabel("Exact recovery")
    bx.set_ylabel("Mean BER where observed")
    ax.legend(loc="lower left")
    figure("capacity_robustness", fig)
    return out


def ablation():
    groups = ("phase1_results", "phase1_results_positions_0_2", "phase1_results_positions_0_2_tie_fixed")
    output = []
    for directory in groups:
        config = json.loads((ROOT / directory / "config.json").read_text())
        rows = read_csv(ROOT / directory / "phase1_trials.csv")
        for q in sorted({int(r["quality"]) for r in rows}, reverse=True):
            subset = [r for r in rows if int(r["quality"]) == q]
            output.append(dict(run=directory, pair_indices=config.get("pair_indices", "0,1,2,3"),
                               gap=config["gap"], embedded_bits=config["bits"], jpeg_quality=q,
                               n=len(subset), total_errors=sum(int(r["bit_errors"]) for r in subset),
                               aggregate_ber=sum(int(r["bit_errors"]) for r in subset) /
                               sum(int(r["embedded_bits"]) for r in subset),
                               zero_error_covers=sum(int(r["bit_errors"]) == 0 for r in subset)))
    write_csv("phase1_ablation.csv", output)
    texture = []
    final_rows = read_csv(ROOT / "phase1_results_positions_0_2_tie_fixed" / "phase1_trials.csv")
    config = json.loads((ROOT / "phase1_results_positions_0_2_tie_fixed" / "config.json").read_text())
    source = Path(config["covers_dir"])
    for cover_name in dict.fromkeys(r["cover"] for r in final_rows):
        coefficients = luminance_coefficients(jpeglib.read_dct(str(source / cover_name))).astype(np.float64)
        ac = coefficients.reshape(-1, 64)[:, 1:]
        texture.append(dict(cover=cover_name, mean_abs_ac=float(np.mean(np.abs(ac))),
                            mean_ber=float(np.mean([float(r["ber"]) for r in final_rows if r["cover"] == cover_name]))))
    rho, pvalue = spearmanr([r["mean_abs_ac"] for r in texture], [r["mean_ber"] for r in texture])
    for row in texture:
        row["spearman_rho_all_covers"] = rho
        row["spearman_pvalue_all_covers"] = pvalue
    write_csv("cover_texture.csv", texture)
    fig, ax = plt.subplots(figsize=(5.8, 2.7))
    for directory, marker, line in zip(groups, ("o", "s", "^"), ("-", "--", ":")):
        series = sorted([r for r in output if r["run"] == directory], key=lambda r: r["jpeg_quality"])
        ax.plot([r["jpeg_quality"] for r in series], [r["aggregate_ber"] for r in series],
                color="black", marker=marker, linestyle=line, label=directory.replace("phase1_results", "Phase 1"))
    ax.set(xlabel="JPEG quality", ylabel="Aggregate bit error rate")
    ax.legend()
    ax.grid(alpha=.3)
    figure("phase1_ablation", fig)
    return output, texture, float(rho), float(pvalue)


def detectability_feature(path, pair_indices):
    y = luminance_coefficients(jpeglib.read_dct(str(path))).astype(np.float64)
    margins = []
    for pair_index in pair_indices:
        ar, ac, br, bc = PAIR_POSITIONS[pair_index]
        margins.append(np.abs(y[:, :, ar, ac]) - np.abs(y[:, :, br, bc]))
    return float(np.mean(np.abs(np.concatenate([margin.ravel() for margin in margins]))))


def detectability(covers):
    """LOOCV screen over retained cover/stego pairs, explicitly not rich-model steganalysis."""
    run_specs = []
    for directory in ("phase1_results", "phase1_results_positions_0_2", "phase1_results_positions_0_2_tie_fixed"):
        config = json.loads((ROOT / directory / "config.json").read_text())
        pair_indices = tuple(int(x) for x in str(config.get("pair_indices", "0,1,2,3")).split(","))
        run_specs.append((directory, ROOT / directory, pair_indices, int(config["bits"])))
    run_specs.append(("phase3_aes_gcm_results_q95", ROOT / "phase3_aes_gcm_results", (0, 2), 384))
    records, summary = [], []
    for run_name, directory, pair_indices, payload_bits in run_specs:
        pairs = []
        for index, (name, cover) in enumerate(covers, 1):
            if run_name == "phase3_aes_gcm_results_q95":
                stego = directory / f"{index:02d}_{cover.stem}_q95_stego.jpg"
            else:
                stego = directory / f"{index:02d}_{cover.stem}_stego.jpg"
            if not stego.is_file():
                continue
            pairs.append(dict(run=run_name, cover=name, payload_bits=payload_bits,
                              pair_indices=",".join(map(str, pair_indices)),
                              cover_feature=detectability_feature(cover, pair_indices),
                              stego_feature=detectability_feature(stego, pair_indices)))
        tp = tn = 0
        for i, row in enumerate(pairs):
            others = [r for j, r in enumerate(pairs) if j != i]
            clean = np.array([r["cover_feature"] for r in others])
            hidden = np.array([r["stego_feature"] for r in others])
            direction = np.sign(hidden.mean() - clean.mean()) or 1
            threshold = (np.median(hidden) + np.median(clean)) / 2
            cover_pred = bool((row["cover_feature"] - threshold) * direction > 0)
            stego_pred = bool((row["stego_feature"] - threshold) * direction > 0)
            row["cover_predicted_stego"] = int(cover_pred)
            row["stego_predicted_stego"] = int(stego_pred)
            tn += int(not cover_pred)
            tp += int(stego_pred)
            records.extend([dict(row, sample="cover"), dict(row, sample="stego")])
        n = len(pairs)
        summary.append(dict(run=run_name, payload_bits=payload_bits, pair_indices=",".join(map(str, pair_indices)),
                            n_pairs=n, true_negative=tn, true_positive=tp,
                            balanced_accuracy=(tn / n + tp / n) / 2 if n else ""))
    write_csv("paired_detectability.csv", records)
    write_csv("detectability_summary.csv", summary)
    fig, ax = plt.subplots(figsize=(5.8, 2.5))
    x = np.arange(len(summary))
    values = [row["balanced_accuracy"] for row in summary]
    bars = ax.bar(x, values, color="#777777", edgecolor="black", hatch="//")
    for bar, row in zip(bars, summary):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + .02,
                f"{100*row['balanced_accuracy']:.0f}%", ha="center", va="bottom", fontsize=7)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Balanced accuracy")
    ax.set_xticks(x, ["512-bit\nall pairs", "256-bit\n0,2", "256-bit\ntie-fixed", "384-bit\nAES-GCM"])
    ax.grid(axis="y", alpha=.3)
    ax.set_axisbelow(True)
    figure("detectability_screen", fig)
    return summary


def latex_escape(value):
    return str(value).replace("_", r"\_").replace("%", r"\%")


def write_latex_supplement(transform_summary, capacity_rows, ablation_rows, detectability_rows,
                           texture_rows, visual, delivered_quality, dimension_rows,
                           failure_rows):
    """Emit numeric table rows/macros so manuscript values remain generated, not hand-edited."""
    def f(value, digits=3):
        return f"{float(value):.{digits}f}" if value not in ("", None) else "--"
    row_end = r" \\"

    transform_rows = []
    for row in transform_summary:
        transform_rows.append(
            f"{latex_escape(row['transform'])} & {latex_escape(row['mechanism'])} & "
            f"{row['successes']}/{row['n']} & {100*float(row['recovery_rate']):.1f}\\% & "
            f"{f(row['mean_ber'], 4)} & {f(row['mean_aligned_psnr'], 1)} & {f(row['mean_aligned_ssim'], 3)} " + row_end)
    capacity_table = []
    for row in capacity_rows:
        payload = f"{row['min_bytes']}" if row['min_bytes'] == row['max_bytes'] else f"{row['min_bytes']}--{row['max_bytes']}"
        capacity_table.append(
            f"{latex_escape(row['platform'])} & {latex_escape(row['payload_class'])} & {payload} & "
            f"{row['successes']}/{row['n']} & {f(row['mean_observed_ber'], 4)} " + row_end)
    selected = []
    ablation_labels = {
        "phase1_results": "Phase 1 all pairs",
        "phase1_results_positions_0_2": "Phase 1 0,2",
        "phase1_results_positions_0_2_tie_fixed": "Phase 1 0,2 tie-fixed",
    }
    for run in sorted({row["run"] for row in ablation_rows}):
        group = [row for row in ablation_rows if row["run"] == run]
        q50 = next(row for row in group if int(row["jpeg_quality"]) == 50)
        q95 = next(row for row in group if int(row["jpeg_quality"]) == 95)
        selected.append(
            f"{latex_escape(ablation_labels.get(run, run))} & {latex_escape(q50['pair_indices'])} & {q50['embedded_bits']} & "
            f"{f(q95['aggregate_ber'], 4)} & {f(q50['aggregate_ber'], 4)} & {q50['zero_error_covers']}/15 " + row_end)
    detect_rows = []
    detect_labels = {
        "phase1_results": "Phase 1 all pairs",
        "phase1_results_positions_0_2": "Phase 1 0,2",
        "phase1_results_positions_0_2_tie_fixed": "Phase 1 0,2 tie-fixed",
        "phase3_aes_gcm_results_q95": "Phase 3 AES-GCM",
    }
    for row in detectability_rows:
        detect_rows.append(
            f"{latex_escape(detect_labels.get(row['run'], row['run']))} & {row['payload_bits']} & {row['true_negative']}/{row['n_pairs']} & "
            f"{row['true_positive']}/{row['n_pairs']} & {100*float(row['balanced_accuracy']):.1f}\\% " + row_end)
    texture_rho, texture_p = (float(texture_rows[0]["spearman_rho_all_covers"]),
                               float(texture_rows[0]["spearman_pvalue_all_covers"]))
    visual_psnr = float(np.mean([float(row["psnr"]) for row in visual if math.isfinite(float(row["psnr"]))]))
    visual_ssim = float(np.mean([float(row["ssim"]) for row in visual]))
    quality_rows = []
    for platform in sorted({row["platform"] for row in delivered_quality}):
        group = [row for row in delivered_quality if row["platform"] == platform]
        finite_psnr = [float(row["stego_to_delivered_psnr"]) for row in group
                       if str(row["stego_to_delivered_psnr"]).lower() not in {"inf", "infinity"}]
        quality_rows.append(
            f"{latex_escape(platform)} & {len(group)} & {len(group)-len(finite_psnr)} & "
            f"{f(np.mean(finite_psnr), 1) if finite_psnr else '--'} & "
            f"{f(np.mean([float(row['stego_to_delivered_ssim']) for row in group]), 3)} & "
            f"{f(np.mean([float(row['width_ratio']) for row in group]), 3)} " + row_end)
    dim_rows = []
    dim_notes = {
        "no row-level delivered dimensions available": "no CSV dimensions",
        "artifact pairing available": "artifact pairs only",
    }
    for row in dimension_rows:
        dim_rows.append(
            f"{latex_escape(row['platform'])} & {row['csv_dimension_rows']} & {row['artifact_paired_rows']} & "
            f"{f(row['mean_width_ratio'], 3)} & {latex_escape(dim_notes.get(row['note'], row['note']))} " + row_end)
    failure_categories = ("success", "fixed_grid_extraction_failed",
                          "reed_solomon_decode_failed", "capacity_failure",
                          "authentication_failed")
    failure_counts = {}
    for row in failure_rows:
        failure_counts.setdefault(row["platform"], {category: 0 for category in failure_categories})
        failure_counts[row["platform"]][row["outcome"]] = int(row["n"])
    failure_order = ("discord", "whatsapp_document", "telegram", "twitter",
                     "instagram", "whatsapp_image")
    failure_labels = {
        "discord": "Discord",
        "whatsapp_document": "WA Doc",
        "telegram": "Telegram",
        "twitter": "X",
        "instagram": "Instagram",
        "whatsapp_image": "WA Image",
    }
    failure_table = []
    for platform in failure_order:
        counts = failure_counts.get(platform, {category: 0 for category in failure_categories})
        failure_table.append(
            f"{failure_labels[platform]} & {counts['success']} & "
            f"{counts['fixed_grid_extraction_failed']} & "
            f"{counts['reed_solomon_decode_failed']} & {counts['capacity_failure']} & "
            f"{counts['authentication_failed']} " + row_end)
    content_parts = [
        "% Generated by offline_paper_analysis.py; do not hand-edit numeric values.",
        r"\newcommand{\OfflineTransformRows}{%",
        "\n".join(transform_rows),
        "}",
        r"\newcommand{\OfflineCapacityRows}{%",
        "\n".join(capacity_table),
        "}",
        r"\newcommand{\OfflineAblationRows}{%",
        "\n".join(selected),
        "}",
        r"\newcommand{\OfflineDetectabilityRows}{%",
        "\n".join(detect_rows),
        "}",
        r"\newcommand{\OfflineQualityRows}{%",
        "\n".join(quality_rows),
        "}",
        r"\newcommand{\OfflineDimensionRows}{%",
        "\n".join(dim_rows),
        "}",
        r"\newcommand{\OfflineFailureRows}{%",
        "\n".join(failure_table),
        "}",
        rf"\newcommand{{\OfflineMeanCoverPSNR}}{{{visual_psnr:.1f}}}",
        rf"\newcommand{{\OfflineMeanCoverSSIM}}{{{visual_ssim:.3f}}}",
        rf"\newcommand{{\OfflineTextureRho}}{{{texture_rho:.3f}}}",
        rf"\newcommand{{\OfflineTextureP}}{{{texture_p:.3f}}}",
        rf"\newcommand{{\OfflineDimensionCoverage}}{{{sum(int(r['csv_dimension_rows']) for r in dimension_rows)}}}",
    ]
    content = "\n".join(content_parts) + "\n"
    (OUT / "generated_offline_results.tex").write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-controlled", action="store_true", help="use existing controlled CSV after a completed run")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    manifest = json.loads((ROOT / "phase1_results_positions_0_2_tie_fixed" / "config.json").read_text())
    source = Path(manifest["covers_dir"])
    trial_rows = read_csv(ROOT / "phase5_results" / "platform_trials.csv")
    names = list(dict.fromkeys(r["cover_name"] for r in trial_rows if r["platform"] == "discord"))
    covers = [(name, source / name) for name in names]
    if len(covers) != 15 or any(not path.is_file() for _, path in covers):
        raise FileNotFoundError("15 exact source covers from the structured manifest are required")
    if args.skip_controlled:
        transform_rows = read_csv(OUT / "controlled_transforms.csv")
        visual = read_csv(OUT / "visual_quality.csv")
    else:
        transform_rows, visual = controlled(covers)
    failure_rows, delivered_quality, dimension_rows = platform_analysis(trial_rows, covers)
    capacity_rows = capacity(trial_rows)
    ablation_rows, texture_rows, texture_rho, texture_pvalue = ablation()
    detectability_rows = detectability(covers)
    write_latex_supplement(
        read_csv(OUT / "controlled_transform_summary.csv"), capacity_rows, ablation_rows,
        detectability_rows, texture_rows, visual, delivered_quality, dimension_rows,
        failure_rows,
    )
    digest = {
        "controlled": {kind: {"success": sum(int(r["success"]) for r in transform_rows if r["transform"] == kind),
                              "n": sum(r["transform"] == kind for r in transform_rows)}
                       for kind in sorted({r["transform"] for r in transform_rows})},
        "detectability": detectability_rows,
        "dimension_caveat": "CSV dimensions empty; delivered filenames do not identify their original covers. No platform dimension ratio is estimable.",
        "ablation_caveat": "Historical runs differ in pair subset, bit count, and decoder tie rule; gap remains 24. Not a factorial causal ablation.",
        "texture_association": {"spearman_rho": texture_rho, "pvalue": texture_pvalue, "n": len(texture_rows)},
        "visual_quality": {"cover_to_stego_n": len(visual),
                           "mean_psnr": float(np.mean([float(r["psnr"]) for r in visual if math.isfinite(float(r["psnr"]))])),
                           "mean_ssim": float(np.mean([float(r["ssim"]) for r in visual]))},
        "delivered_quality": {platform: {"n": len([r for r in delivered_quality if r["platform"] == platform]),
                                          "identical_pixel_pairs": sum(str(r["stego_to_delivered_psnr"]).lower() in {"inf", "infinity"} for r in delivered_quality if r["platform"] == platform),
                                          "mean_finite_aligned_psnr": float(np.mean([float(r["stego_to_delivered_psnr"]) for r in delivered_quality if r["platform"] == platform and str(r["stego_to_delivered_psnr"]).lower() not in {"inf", "infinity"}])),
                                          "mean_aligned_ssim": float(np.mean([float(r["stego_to_delivered_ssim"]) for r in delivered_quality if r["platform"] == platform])),
                                          "mean_width_ratio": float(np.mean([r["width_ratio"] for r in delivered_quality if r["platform"] == platform]))}
                              for platform in sorted({r["platform"] for r in delivered_quality})},
        "ssim_caveat": "Local 11x11 RGB SSIM. Delivered images are matched one-to-one by thumbnails and source images are resized to returned dimensions before aligned PSNR/SSIM; this is an artifact-level pairing, not a canonical CSV join.",
    }
    (OUT / "summary.json").write_text(json.dumps(digest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(digest, indent=2))


if __name__ == "__main__":
    main()
