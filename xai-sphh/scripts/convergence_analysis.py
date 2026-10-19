#!/usr/bin/env python3
"""Task 1: Per-domain budgets from convergence curves.

Reads the 24 Assessment 4 traces, computes best-so-far at each iteration,
finds the 95% improvement iteration, and produces:
  - results/budgets/budget_table.csv
  - results/budgets/convergence.png
"""

import csv
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

TRACES_DIR = Path("data/raw/traces")
OUT_DIR = Path("results/budgets")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = ["SAT", "BinPacking", "FlowShop", "TSP", "VRP", "PersonnelScheduling"]
TECHNIQUES = ["SP-CF-LA", "SP-CF-AILTA", "SP-SR-LA", "MP-CF"]
BUDGET_TIERS = [5_000, 10_000, 20_000, 50_000, 100_000]
PS_CAP = 10_000  # Cap for PersonnelScheduling (Task 0 found no speedup)

# Estimated seconds per application (from Task 0 profiling and SAT test run)
DOMAIN_COST_S = {
    "SAT": 0.004,
    "BinPacking": 0.003,
    "FlowShop": 0.005,
    "TSP": 0.004,
    "VRP": 0.005,
    "PersonnelScheduling": 0.212,
}


def load_best_so_far(trace_path):
    """Load best_so_far column from a trace CSV, returning list of floats."""
    bsf = []
    with open(trace_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            bsf.append(float(row["best_so_far"]))
    return bsf


def find_95_pct_iteration(bsf):
    """Find the iteration at which 95% of total improvement is reached.

    Improvement is measured as (start - final) for minimisation.
    Returns the 0-based iteration index.
    """
    if not bsf:
        return 0
    start = bsf[0]
    final = bsf[-1]
    total_improvement = start - final
    if total_improvement <= 0:
        # No improvement or worsening: convergence at iteration 0
        return 0
    threshold = start - 0.95 * total_improvement  # 95% of improvement reached
    for i, val in enumerate(bsf):
        if val <= threshold:
            return i
    return len(bsf) - 1


def round_up_to_tier(iteration):
    """Round up to the nearest budget tier."""
    for tier in BUDGET_TIERS:
        if iteration <= tier:
            return tier
    return BUDGET_TIERS[-1]


def main():
    # Collect data: domain -> technique -> (bsf list, 95% iter)
    data = defaultdict(dict)

    for domain in DOMAINS:
        for technique in TECHNIQUES:
            stem = f"{technique}_{domain}_0_42"
            trace_path = TRACES_DIR / f"trace_{stem}.csv"
            if not trace_path.exists():
                print(f"WARNING: missing trace {trace_path}", file=sys.stderr)
                continue
            bsf = load_best_so_far(trace_path)
            iter_95 = find_95_pct_iteration(bsf)
            data[domain][technique] = {
                "bsf": bsf,
                "iter_95": iter_95,
                "n_iters": len(bsf),
            }

    # Compute per-domain budgets
    budget_rows = []
    domain_budgets = {}

    for domain in DOMAINS:
        techs = data.get(domain, {})
        if not techs:
            continue

        max_iter_95 = max(t["iter_95"] for t in techs.values())
        chosen = round_up_to_tier(max_iter_95)

        # Apply PS cap
        capped = False
        if domain == "PersonnelScheduling" and chosen > PS_CAP:
            chosen = PS_CAP
            capped = True

        domain_budgets[domain] = chosen

        # Estimate CPU hours for 10 seeds x 4 techniques
        cost_per_app = DOMAIN_COST_S.get(domain, 0.005)
        total_apps = chosen * 4 * 10  # 4 techniques, 10 seeds
        cpu_hours = total_apps * cost_per_app / 3600

        row = {
            "domain": domain,
            "budget_iters": chosen,
            "max_95pct_iter": max_iter_95,
            "capped": "yes" if capped else "no",
            "est_cpu_hours": round(cpu_hours, 2),
        }
        # Per-technique 95% iterations
        for technique in TECHNIQUES:
            if technique in techs:
                row[f"iter_95_{technique}"] = techs[technique]["iter_95"]
            else:
                row[f"iter_95_{technique}"] = ""
        budget_rows.append(row)

    # Write budget_table.csv
    csv_path = OUT_DIR / "budget_table.csv"
    fieldnames = ["domain", "budget_iters", "max_95pct_iter", "capped", "est_cpu_hours"]
    fieldnames += [f"iter_95_{t}" for t in TECHNIQUES]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(budget_rows)
    print(f"Written: {csv_path}")

    # Print table
    print()
    print(f"{'Domain':<22} {'Budget':>8} {'Max95%':>8} {'Capped':>7} {'CPU-h':>7}"
          + "".join(f" {t:>12}" for t in TECHNIQUES))
    print("-" * (22 + 8 + 8 + 7 + 7 + 12 * len(TECHNIQUES) + 5 * len(TECHNIQUES)))
    total_cpu = 0
    for row in budget_rows:
        parts = [
            f"{row['domain']:<22}",
            f"{row['budget_iters']:>8}",
            f"{row['max_95pct_iter']:>8}",
            f"{row['capped']:>7}",
            f"{row['est_cpu_hours']:>7}",
        ]
        for t in TECHNIQUES:
            v = row.get(f"iter_95_{t}", "")
            parts.append(f"{v:>12}")
        print(" ".join(parts))
        total_cpu += row["est_cpu_hours"]
    print(f"\nTotal estimated CPU hours (10 seeds x 4 techniques): {total_cpu:.1f}")

    # Plot convergence curves
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    axes = axes.flatten()
    colours = {"SP-CF-LA": "#1f77b4", "SP-CF-AILTA": "#ff7f0e",
               "SP-SR-LA": "#2ca02c", "MP-CF": "#d62728"}

    for idx, domain in enumerate(DOMAINS):
        ax = axes[idx]
        techs = data.get(domain, {})
        budget = domain_budgets.get(domain, 100_000)

        for technique in TECHNIQUES:
            if technique not in techs:
                continue
            bsf = techs[technique]["bsf"]
            iterations = list(range(len(bsf)))
            ax.plot(iterations, bsf, label=technique,
                    color=colours[technique], linewidth=0.8, alpha=0.9)

        # Vertical line at chosen budget
        ax.axvline(x=budget, color="black", linestyle="--", linewidth=1.2,
                   label=f"Budget = {budget:,}")

        ax.set_title(domain, fontsize=11, fontweight="bold")
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Best-so-far objective")
        ax.legend(fontsize=7, loc="upper right")
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(
            lambda x, p: f"{x/1000:.0f}k" if x >= 1000 else f"{x:.0f}"))

    plt.suptitle("Convergence Curves with Per-Domain Budgets", fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig_path = OUT_DIR / "convergence.png"
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Written: {fig_path}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    main()
