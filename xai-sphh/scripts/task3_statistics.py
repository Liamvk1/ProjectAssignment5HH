#!/usr/bin/env python3
"""Task 3: Results and statistics from the replication run.

Reads the 240 trace files (or however many exist) from results/a5/traces/,
extracts the final objective per run, and produces:
  - Per-domain summary tables (median, IQR, mean, SD, min, max)
  - Per-domain box plots
  - Wilcoxon signed-rank tests vs SP-SR-LA baseline with Holm correction
  - Vargha-Delaney A12 effect sizes
  - Cross-domain ranking (mean rank, normalised scores, Friedman test)
"""

import csv
import json
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

TRACES_DIR = Path("results/a5/traces")
OUT_DIR = Path("results/a5/statistics")
FIG_DIR = Path("results/a5/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = ["SAT", "BinPacking", "FlowShop", "TSP", "VRP", "PersonnelScheduling"]
TECHNIQUES = ["SP-SR-LA", "SP-CF-LA", "SP-CF-AILTA", "MP-CF"]
SEEDS_FILE = Path("config/seeds.txt")


def load_seeds():
    return [int(s.strip()) for s in SEEDS_FILE.read_text().strip().split("\n")]


def get_final_objective(trace_path):
    """Read the last row's best_so_far from a trace CSV."""
    last_bsf = None
    with open(trace_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            last_bsf = float(row["best_so_far"])
    return last_bsf


def vargha_delaney_a12(x, y):
    """Compute Vargha-Delaney A12 effect size.

    A12 > 0.5 means x tends to have larger values than y.
    For minimisation, A12 < 0.5 means x is better.
    """
    nx, ny = len(x), len(y)
    r = stats.rankdata(np.concatenate([x, y]))
    r1 = r[:nx]
    a12 = (np.sum(r1) - nx * (nx + 1) / 2) / (nx * ny)
    return a12


def holm_correction(p_values):
    """Apply Holm-Bonferroni correction to a list of p-values.

    Returns corrected p-values (capped at 1.0).
    """
    n = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    corrected = [0.0] * n
    for rank, (orig_idx, p) in enumerate(indexed):
        corrected[orig_idx] = min(p * (n - rank), 1.0)
    # Enforce monotonicity
    for rank in range(1, n):
        orig_idx = indexed[rank][0]
        prev_idx = indexed[rank - 1][0]
        corrected[orig_idx] = max(corrected[orig_idx], corrected[prev_idx])
    return corrected


def main():
    seeds = load_seeds()

    # Collect final objectives: domain -> technique -> [objectives by seed]
    results = defaultdict(lambda: defaultdict(dict))
    missing = []

    for domain in DOMAINS:
        for technique in TECHNIQUES:
            for seed in seeds:
                stem = f"{technique}_{domain}_0_{seed}"
                trace_path = TRACES_DIR / f"trace_{stem}.csv"
                if trace_path.exists():
                    obj = get_final_objective(trace_path)
                    results[domain][technique][seed] = obj
                else:
                    missing.append(stem)

    if missing:
        print(f"WARNING: {len(missing)} missing traces", file=sys.stderr)
        for m in missing[:10]:
            print(f"  {m}", file=sys.stderr)
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more", file=sys.stderr)

    # --- Per-domain summary ---
    summary_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            vals = sorted(results[domain][technique].values())
            if not vals:
                continue
            arr = np.array(vals)
            q1, q3 = np.percentile(arr, [25, 75])
            summary_rows.append({
                "domain": domain,
                "technique": technique,
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
    fields = ["domain", "technique", "n", "median", "iqr_low", "iqr_high",
              "mean", "std", "min", "max"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summary_rows)
    print(f"Written: {csv_path}")

    # --- Wilcoxon tests vs SP-SR-LA ---
    test_rows = []
    for domain in DOMAINS:
        baseline = results[domain]["SP-SR-LA"]
        comparisons = []
        for technique in TECHNIQUES:
            if technique == "SP-SR-LA":
                continue
            other = results[domain][technique]
            # Pair by seed
            common_seeds = sorted(set(baseline.keys()) & set(other.keys()))
            if len(common_seeds) < 5:
                continue
            x = np.array([baseline[s] for s in common_seeds])
            y = np.array([other[s] for s in common_seeds])
            diffs = x - y
            # Wilcoxon signed-rank (two-sided)
            if np.all(diffs == 0):
                stat, p = 0, 1.0
            else:
                stat, p = stats.wilcoxon(x, y, alternative="two-sided")
            a12 = vargha_delaney_a12(y, x)  # A12 < 0.5 means y (other) is better (lower)
            comparisons.append({
                "domain": domain,
                "technique": technique,
                "n_pairs": len(common_seeds),
                "wilcoxon_stat": stat,
                "p_value": p,
                "a12": a12,
            })

        # Holm correction within domain
        if comparisons:
            p_vals = [c["p_value"] for c in comparisons]
            corrected = holm_correction(p_vals)
            for c, cp in zip(comparisons, corrected):
                c["p_corrected"] = cp
                c["significant"] = "yes" if cp < 0.05 else "no"
            test_rows.extend(comparisons)

    csv_path = OUT_DIR / "wilcoxon_tests.csv"
    fields = ["domain", "technique", "n_pairs", "wilcoxon_stat", "p_value",
              "p_corrected", "a12", "significant"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(test_rows)
    print(f"Written: {csv_path}")

    # --- Box plots ---
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    axes = axes.flatten()
    for idx, domain in enumerate(DOMAINS):
        ax = axes[idx]
        data = []
        labels = []
        for technique in TECHNIQUES:
            vals = list(results[domain][technique].values())
            if vals:
                data.append(vals)
                labels.append(technique.replace("SP-", "").replace("MP-", "MP-"))
        if data:
            bp = ax.boxplot(data, patch_artist=True)
            ax.set_xticklabels(labels)
            colours = ["#2ca02c", "#1f77b4", "#ff7f0e", "#d62728"]
            for patch, c in zip(bp["boxes"], colours):
                patch.set_facecolor(c)
                patch.set_alpha(0.6)
        ax.set_title(domain, fontsize=11, fontweight="bold")
        ax.set_ylabel("Final objective")
        ax.tick_params(axis="x", rotation=30)
    plt.suptitle("Final Objective by Technique (per domain)", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig_path = FIG_DIR / "boxplots_per_domain.png"
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Written: {fig_path}")

    # --- Cross-domain analysis ---
    # Rank within each domain by median (1 = best = lowest)
    domain_medians = {}
    for domain in DOMAINS:
        medians = {}
        for technique in TECHNIQUES:
            vals = list(results[domain][technique].values())
            if vals:
                medians[technique] = np.median(vals)
        domain_medians[domain] = medians

    rank_rows = []
    all_ranks = defaultdict(list)
    all_norm = defaultdict(list)

    for domain in DOMAINS:
        medians = domain_medians[domain]
        if not medians:
            continue
        # Rank (1 = best = lowest). Average ties.
        sorted_techs = sorted(medians.items(), key=lambda x: x[1])
        ranks = {}
        i = 0
        while i < len(sorted_techs):
            j = i
            while j < len(sorted_techs) and sorted_techs[j][1] == sorted_techs[i][1]:
                j += 1
            avg_rank = (i + 1 + j) / 2  # average rank for ties
            for k in range(i, j):
                ranks[sorted_techs[k][0]] = avg_rank
            i = j

        # Normalise to [0, 1]: (value - best) / (worst - best)
        best = min(medians.values())
        worst = max(medians.values())
        span = worst - best if worst != best else 1.0
        norm = {t: (v - best) / span for t, v in medians.items()}

        for technique in TECHNIQUES:
            if technique in medians:
                rank_rows.append({
                    "domain": domain,
                    "technique": technique,
                    "median": medians[technique],
                    "rank": ranks[technique],
                    "normalised": norm[technique],
                })
                all_ranks[technique].append(ranks[technique])
                all_norm[technique].append(norm[technique])

    csv_path = OUT_DIR / "cross_domain_ranks.csv"
    fields = ["domain", "technique", "median", "rank", "normalised"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rank_rows)

    # Add mean rank and mean normalised score
    mean_rank_rows = []
    for technique in TECHNIQUES:
        if all_ranks[technique]:
            mean_rank_rows.append({
                "technique": technique,
                "mean_rank": np.mean(all_ranks[technique]),
                "mean_normalised": np.mean(all_norm[technique]),
            })
    with open(csv_path, "a") as f:
        f.write("\n# Mean across domains\n")
        for row in mean_rank_rows:
            f.write(f"# {row['technique']}: mean_rank={row['mean_rank']:.2f}, "
                    f"mean_normalised={row['mean_normalised']:.4f}\n")
    print(f"Written: {csv_path}")

    # --- Friedman test ---
    friedman_path = OUT_DIR / "friedman_test.txt"
    # Build rank matrix: domains x techniques
    rank_matrix = []
    for domain in DOMAINS:
        domain_ranks = []
        for technique in TECHNIQUES:
            found = [r for r in rank_rows
                     if r["domain"] == domain and r["technique"] == technique]
            if found:
                domain_ranks.append(found[0]["rank"])
            else:
                domain_ranks.append(np.nan)
        rank_matrix.append(domain_ranks)
    rank_matrix = np.array(rank_matrix)

    with open(friedman_path, "w") as f:
        f.write("Friedman Test: techniques as treatments, domains as blocks\n")
        f.write(f"Techniques: {TECHNIQUES}\n")
        f.write(f"Domains: {DOMAINS}\n\n")

        f.write("Rank matrix (rows=domains, cols=techniques):\n")
        for i, domain in enumerate(DOMAINS):
            f.write(f"  {domain}: {rank_matrix[i]}\n")
        f.write(f"\nMean ranks: {rank_matrix.mean(axis=0)}\n\n")

        if rank_matrix.shape[0] >= 3:
            # Friedman test
            try:
                stat, p = stats.friedmanchisquare(*[rank_matrix[:, i]
                                                     for i in range(rank_matrix.shape[1])])
                f.write(f"Friedman chi-squared = {stat:.4f}, p = {p:.6f}\n")
                if p < 0.05:
                    f.write("Result: SIGNIFICANT (p < 0.05). Proceed with post-hoc tests.\n\n")
                    # Nemenyi post-hoc (using critical difference)
                    k = len(TECHNIQUES)
                    n = len(DOMAINS)
                    # Holm-corrected pairwise Wilcoxon on ranks
                    f.write("Holm-corrected pairwise comparisons (by mean rank difference):\n")
                    pairs = list(combinations(range(k), 2))
                    p_vals_posthoc = []
                    pair_labels = []
                    for i, j in pairs:
                        ri = rank_matrix[:, i]
                        rj = rank_matrix[:, j]
                        diffs = ri - rj
                        if np.all(diffs == 0):
                            p_ph = 1.0
                        else:
                            _, p_ph = stats.wilcoxon(ri, rj)
                        p_vals_posthoc.append(p_ph)
                        pair_labels.append(f"{TECHNIQUES[i]} vs {TECHNIQUES[j]}")

                    corrected_ph = holm_correction(p_vals_posthoc)
                    for label, p_raw, p_corr in sorted(
                            zip(pair_labels, p_vals_posthoc, corrected_ph),
                            key=lambda x: x[1]):
                        sig = "***" if p_corr < 0.01 else ("**" if p_corr < 0.05 else "")
                        f.write(f"  {label}: p_raw={p_raw:.4f}, p_corrected={p_corr:.4f} {sig}\n")
                else:
                    f.write("Result: NOT significant (p >= 0.05). "
                            "No evidence of difference between techniques across domains.\n")
            except Exception as e:
                f.write(f"Friedman test failed: {e}\n")
        else:
            f.write("Not enough domains (need >= 3) for Friedman test.\n")

    print(f"Written: {friedman_path}")

    # Print summary
    print("\n=== Per-domain summary ===")
    for domain in DOMAINS:
        print(f"\n{domain}:")
        for row in summary_rows:
            if row["domain"] == domain:
                print(f"  {row['technique']:15s}  n={row['n']:2d}  "
                      f"median={row['median']:12.2f}  IQR=[{row['iqr_low']:.2f}, {row['iqr_high']:.2f}]  "
                      f"mean={row['mean']:12.2f}  std={row['std']:10.2f}")

    print("\n=== Cross-domain mean ranks ===")
    for row in mean_rank_rows:
        print(f"  {row['technique']:15s}  mean_rank={row['mean_rank']:.2f}  "
              f"mean_norm={row['mean_normalised']:.4f}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    main()
