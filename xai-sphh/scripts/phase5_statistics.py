#!/usr/bin/env python3
"""Phase 5: Statistical analysis of XAI variant experiments.

Reads trace files from results/rq2/traces/, extracts the final best_so_far
per run, and produces:
  - Per-domain summary tables (median, IQR, mean, SD) for all variants
  - Wilcoxon signed-rank tests (paired by seed) with Holm correction:
      RQ2: XAI vs BASE
      RQ3: XAI-LODO vs BASE, XAI-LODO vs XAI
      RQ4: XAI vs RAND, XAI vs STAT
  - Vargha-Delaney A12 effect sizes
  - Friedman test across all 5 variants per base technique
  - Box plots per domain

Works with partial results — pairs only seeds where both variants exist.
"""

import csv
import os
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scipy import stats

TRACES_DIR = Path("results/rq2/traces")
OUT_DIR = Path("results/rq2/statistics")
FIG_DIR = Path("results/rq2/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = ["SAT", "BinPacking", "FlowShop", "TSP", "VRP", "PersonnelScheduling"]
SEEDS = [11, 22, 33, 44, 55, 66, 77, 88, 99, 111]

BASE_TECHNIQUES = ["SP-CF-AILTA", "MP-CF"]
SUFFIXES = ["", "-XAI", "-XAI-LODO", "-RAND", "-STAT"]


def get_final_objective(trace_path):
    """Read the last row's best_so_far from a trace CSV.
    Uses tail-read for speed — only reads the header and last line."""
    with open(trace_path, "rb") as f:
        # Read header to find column index
        header = f.readline().decode().strip().split(",")
        try:
            bsf_idx = header.index("best_so_far")
        except ValueError:
            return None

        # Seek to end and read last line
        f.seek(0, 2)
        fsize = f.tell()
        pos = fsize - 2
        while pos > 0:
            f.seek(pos)
            if f.read(1) == b"\n":
                break
            pos -= 1

        last_line = f.readline().decode().strip()
        if not last_line:
            return None

        cols = last_line.split(",")
        if bsf_idx >= len(cols):
            return None
        try:
            return float(cols[bsf_idx])
        except (ValueError, IndexError):
            return None


def vargha_delaney_a12(x, y):
    """A12 effect size. A12 < 0.5 means x is better (lower) for minimisation."""
    nx, ny = len(x), len(y)
    r = stats.rankdata(np.concatenate([x, y]))
    r1 = r[:nx]
    return (np.sum(r1) - nx * (nx + 1) / 2) / (nx * ny)


def a12_magnitude(a12):
    """Classify A12 effect size magnitude."""
    d = abs(a12 - 0.5)
    if d < 0.06:
        return "negligible"
    elif d < 0.14:
        return "small"
    elif d < 0.21:
        return "medium"
    else:
        return "large"


def holm_correction(p_values):
    """Holm-Bonferroni correction. Returns corrected p-values."""
    n = len(p_values)
    if n == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    corrected = [0.0] * n
    for rank, (orig_idx, p) in enumerate(indexed):
        corrected[orig_idx] = min(p * (n - rank), 1.0)
    for rank in range(1, n):
        orig_idx = indexed[rank][0]
        prev_idx = indexed[rank - 1][0]
        corrected[orig_idx] = max(corrected[orig_idx], corrected[prev_idx])
    return corrected


def wilcoxon_safe(x, y):
    """Wilcoxon signed-rank with fallback for identical arrays."""
    diffs = x - y
    if np.all(diffs == 0):
        return 0.0, 1.0
    try:
        stat, p = stats.wilcoxon(x, y, alternative="two-sided")
        return stat, p
    except ValueError:
        return 0.0, 1.0


def main():
    # Collect final objectives: base -> suffix -> domain -> {seed: obj}
    results = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    found = 0
    missing = 0

    for base in BASE_TECHNIQUES:
        for suffix in SUFFIXES:
            technique = f"{base}{suffix}"
            for domain in DOMAINS:
                for seed in SEEDS:
                    stem = f"{technique}_{domain}_1_{seed}"
                    trace_path = TRACES_DIR / f"trace_{stem}.csv"
                    if trace_path.exists():
                        obj = get_final_objective(trace_path)
                        if obj is not None:
                            results[base][suffix][domain][seed] = obj
                            found += 1
                        else:
                            print(f"  WARN: corrupt trace {trace_path.name}", file=sys.stderr)
                            missing += 1
                            continue
                    else:
                        missing += 1

    print(f"Loaded {found} traces ({missing} missing out of {found + missing})")

    if found == 0:
        print("ERROR: No traces found!", file=sys.stderr)
        sys.exit(1)

    # =========================================================================
    # 1. Per-domain summary
    # =========================================================================
    summary_rows = []
    for base in BASE_TECHNIQUES:
        for suffix in SUFFIXES:
            technique = f"{base}{suffix}"
            for domain in DOMAINS:
                vals = list(results[base][suffix][domain].values())
                if not vals:
                    continue
                arr = np.array(vals)
                q1, q3 = np.percentile(arr, [25, 75])
                summary_rows.append({
                    "base_technique": base,
                    "variant": technique,
                    "domain": domain,
                    "n": len(vals),
                    "median": np.median(arr),
                    "iqr_low": q1,
                    "iqr_high": q3,
                    "mean": np.mean(arr),
                    "std": np.std(arr, ddof=1) if len(arr) > 1 else 0,
                    "min": np.min(arr),
                    "max": np.max(arr),
                })

    csv_path = OUT_DIR / "per_domain_summary.csv"
    fields = ["base_technique", "variant", "domain", "n", "median",
              "iqr_low", "iqr_high", "mean", "std", "min", "max"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summary_rows)
    print(f"Written: {csv_path}")

    # =========================================================================
    # 2. Pairwise Wilcoxon tests (RQ2, RQ3, RQ4)
    # =========================================================================
    # Define comparisons: (label, RQ, suffix_a, suffix_b)
    # suffix_a is tested against suffix_b. A12 < 0.5 means a is better.
    COMPARISONS = [
        # RQ2: Does XAI improve over base?
        ("XAI vs BASE",      "RQ2", "-XAI",      ""),
        # RQ3: Does LODO generalise?
        ("LODO vs BASE",     "RQ3", "-XAI-LODO", ""),
        ("LODO vs XAI",      "RQ3", "-XAI-LODO", "-XAI"),
        # RQ4: Is XAI better than controls?
        ("XAI vs RAND",      "RQ4", "-XAI",      "-RAND"),
        ("XAI vs STAT",      "RQ4", "-XAI",      "-STAT"),
    ]

    test_rows = []
    for base in BASE_TECHNIQUES:
        for domain in DOMAINS:
            comparisons_this = []
            for label, rq, suf_a, suf_b in COMPARISONS:
                data_a = results[base][suf_a][domain]
                data_b = results[base][suf_b][domain]
                common_seeds = sorted(set(data_a.keys()) & set(data_b.keys()))
                if len(common_seeds) < 5:
                    continue

                x = np.array([data_a[s] for s in common_seeds])
                y = np.array([data_b[s] for s in common_seeds])
                stat, p = wilcoxon_safe(x, y)
                a12 = vargha_delaney_a12(x, y)

                comparisons_this.append({
                    "base_technique": base,
                    "domain": domain,
                    "comparison": label,
                    "rq": rq,
                    "variant_a": f"{base}{suf_a}",
                    "variant_b": f"{base}{suf_b}" if suf_b else base,
                    "n_pairs": len(common_seeds),
                    "wilcoxon_stat": stat,
                    "p_value": p,
                    "a12": a12,
                    "a12_magnitude": a12_magnitude(a12),
                    "winner": f"{base}{suf_a}" if a12 < 0.5 else
                              (f"{base}{suf_b}" if suf_b else base) if a12 > 0.5 else "tie",
                })

            # Holm correction within this base+domain group
            if comparisons_this:
                p_vals = [c["p_value"] for c in comparisons_this]
                corrected = holm_correction(p_vals)
                for c, cp in zip(comparisons_this, corrected):
                    c["p_corrected"] = cp
                    c["significant"] = "yes" if cp < 0.05 else "no"
                test_rows.extend(comparisons_this)

    csv_path = OUT_DIR / "wilcoxon_tests.csv"
    fields = ["base_technique", "domain", "comparison", "rq",
              "variant_a", "variant_b", "n_pairs",
              "wilcoxon_stat", "p_value", "p_corrected",
              "a12", "a12_magnitude", "winner", "significant"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(test_rows)
    print(f"Written: {csv_path}")

    # =========================================================================
    # 3. Friedman test per base technique (all 5 variants across 6 domains)
    # =========================================================================
    friedman_rows = []
    for base in BASE_TECHNIQUES:
        # Build median matrix: domains x variants
        variants = [f"{base}{s}" for s in SUFFIXES]
        median_matrix = []
        valid_domains = []

        for domain in DOMAINS:
            row = []
            all_present = True
            for suffix in SUFFIXES:
                vals = list(results[base][suffix][domain].values())
                if vals:
                    row.append(np.median(vals))
                else:
                    all_present = False
                    break
            if all_present:
                median_matrix.append(row)
                valid_domains.append(domain)

        if len(valid_domains) < 3:
            print(f"  {base}: Not enough domains for Friedman test")
            continue

        median_matrix = np.array(median_matrix)

        # Rank within each domain (1 = best = lowest)
        rank_matrix = np.zeros_like(median_matrix)
        for i in range(len(valid_domains)):
            rank_matrix[i] = stats.rankdata(median_matrix[i])

        mean_ranks = rank_matrix.mean(axis=0)

        try:
            chi2, p = stats.friedmanchisquare(*[rank_matrix[:, j]
                                                 for j in range(len(SUFFIXES))])
        except Exception:
            chi2, p = 0, 1.0

        friedman_rows.append({
            "base_technique": base,
            "n_domains": len(valid_domains),
            "friedman_chi2": chi2,
            "friedman_p": p,
            "significant": "yes" if p < 0.05 else "no",
        })

        # Print rank summary
        print(f"\n  {base} Friedman: chi2={chi2:.3f}, p={p:.4f}")
        for j, suffix in enumerate(SUFFIXES):
            variant = f"{base}{suffix}" if suffix else base
            print(f"    {variant:25s}  mean_rank={mean_ranks[j]:.2f}")

    csv_path = OUT_DIR / "friedman_tests.csv"
    fields = ["base_technique", "n_domains", "friedman_chi2",
              "friedman_p", "significant"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(friedman_rows)
    print(f"Written: {csv_path}")

    # =========================================================================
    # 4. Cross-domain rank table
    # =========================================================================
    rank_rows = []
    for base in BASE_TECHNIQUES:
        for domain in DOMAINS:
            medians = {}
            for suffix in SUFFIXES:
                vals = list(results[base][suffix][domain].values())
                if vals:
                    variant = f"{base}{suffix}" if suffix else base
                    medians[variant] = np.median(vals)
            if not medians:
                continue

            sorted_v = sorted(medians.items(), key=lambda x: x[1])
            ranks = {}
            i = 0
            while i < len(sorted_v):
                j = i
                while j < len(sorted_v) and sorted_v[j][1] == sorted_v[i][1]:
                    j += 1
                avg_rank = (i + 1 + j) / 2
                for k in range(i, j):
                    ranks[sorted_v[k][0]] = avg_rank
                i = j

            for variant, med in medians.items():
                rank_rows.append({
                    "base_technique": base,
                    "domain": domain,
                    "variant": variant,
                    "median": med,
                    "rank": ranks[variant],
                })

    csv_path = OUT_DIR / "cross_domain_ranks.csv"
    fields = ["base_technique", "domain", "variant", "median", "rank"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rank_rows)
    print(f"Written: {csv_path}")

    # =========================================================================
    # 5. Box plots
    # =========================================================================
    colours = {
        "": "#2ca02c",
        "-XAI": "#1f77b4",
        "-XAI-LODO": "#9467bd",
        "-RAND": "#ff7f0e",
        "-STAT": "#d62728",
    }

    for base in BASE_TECHNIQUES:
        fig, axes = plt.subplots(2, 3, figsize=(18, 10))
        axes = axes.flatten()
        for idx, domain in enumerate(DOMAINS):
            ax = axes[idx]
            data = []
            labels = []
            box_colours = []
            for suffix in SUFFIXES:
                vals = list(results[base][suffix][domain].values())
                if vals:
                    data.append(vals)
                    label = suffix if suffix else "BASE"
                    labels.append(label)
                    box_colours.append(colours[suffix])

            if data:
                bp = ax.boxplot(data, patch_artist=True)
                ax.set_xticklabels(labels, fontsize=8)
                for patch, c in zip(bp["boxes"], box_colours):
                    patch.set_facecolor(c)
                    patch.set_alpha(0.6)
            ax.set_title(domain, fontsize=11, fontweight="bold")
            ax.set_ylabel("Final objective")
            ax.tick_params(axis="x", rotation=30)

        plt.suptitle(f"{base}: Final Objective by Variant",
                     fontsize=13, fontweight="bold")
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        fig_path = FIG_DIR / f"boxplots_{base}.png"
        plt.savefig(fig_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Written: {fig_path}")

    # =========================================================================
    # 6. RQ summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("RESEARCH QUESTION SUMMARY")
    print("=" * 70)

    for rq in ["RQ2", "RQ3", "RQ4"]:
        rq_tests = [t for t in test_rows if t["rq"] == rq]
        if not rq_tests:
            continue
        print(f"\n--- {rq} ---")
        sig_count = sum(1 for t in rq_tests if t["significant"] == "yes")
        total = len(rq_tests)
        print(f"  Significant results: {sig_count}/{total}")
        for t in rq_tests:
            sig_marker = " ***" if t["significant"] == "yes" else ""
            print(f"  {t['base_technique']:15s} {t['domain']:20s} "
                  f"{t['comparison']:15s}  "
                  f"A12={t['a12']:.3f} ({t['a12_magnitude']:10s})  "
                  f"p_corr={t['p_corrected']:.4f}{sig_marker}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    main()
