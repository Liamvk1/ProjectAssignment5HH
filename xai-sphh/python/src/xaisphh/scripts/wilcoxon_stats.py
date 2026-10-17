"""
Wilcoxon signed-rank tests between technique pairs across seeds, per domain,
with Holm correction.

Takes a CSV of final objectives per run and produces a results table.

Expected input columns: ``technique``, ``domain``, ``instance``, ``seed``,
``final_objective``.

Item 7.
"""

from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from statsmodels.stats.multitest import multipletests


def wilcoxon_pairwise(
    df: pd.DataFrame,
    objective_col: str = "final_objective",
    technique_col: str = "technique",
    domain_col:    str = "domain",
    seed_col:      str = "seed",
    alternative:   str = "two-sided",
) -> pd.DataFrame:
    """Run pairwise Wilcoxon signed-rank tests across techniques, per domain.

    For each (domain, technique_A, technique_B) triplet, the test uses the
    final objectives from all matching seeds as paired observations. A Holm
    correction is then applied across all tests within each domain.

    :param df: dataframe with final objectives per run
    :param objective_col: column carrying the objective value
    :param technique_col: column carrying the technique name
    :param domain_col: column carrying the domain name
    :param seed_col: column carrying the seed
    :param alternative: Wilcoxon alternative hypothesis (default: two-sided)
    :return: dataframe with one row per (domain, pair) and columns
             ``domain``, ``technique_a``, ``technique_b``, ``statistic``,
             ``p_raw``, ``p_holm``, ``reject_holm``
    """
    rows = []
    for domain, dom_df in df.groupby(domain_col):
        techniques = sorted(dom_df[technique_col].unique())
        pairs = list(combinations(techniques, 2))

        pair_rows: list[dict] = []
        for (ta, tb) in pairs:
            a_vals = (
                dom_df[dom_df[technique_col] == ta]
                .sort_values(seed_col)[objective_col].to_numpy()
            )
            b_vals = (
                dom_df[dom_df[technique_col] == tb]
                .sort_values(seed_col)[objective_col].to_numpy()
            )

            # Align on matching seeds.
            a_df = dom_df[dom_df[technique_col] == ta][[seed_col, objective_col]]
            b_df = dom_df[dom_df[technique_col] == tb][[seed_col, objective_col]]
            merged = a_df.merge(b_df, on=seed_col, suffixes=("_a", "_b"))
            if len(merged) < 3:
                pair_rows.append({
                    "domain":      domain,
                    "technique_a": ta,
                    "technique_b": tb,
                    "statistic":   float("nan"),
                    "p_raw":       float("nan"),
                    "n_pairs":     len(merged),
                })
                continue

            diff = merged[f"{objective_col}_a"].to_numpy() - merged[f"{objective_col}_b"].to_numpy()
            if np.all(diff == 0):
                pair_rows.append({
                    "domain":      domain,
                    "technique_a": ta,
                    "technique_b": tb,
                    "statistic":   0.0,
                    "p_raw":       1.0,
                    "n_pairs":     len(merged),
                })
                continue

            try:
                stat, pval = wilcoxon(diff, alternative=alternative)
            except Exception:
                stat, pval = float("nan"), float("nan")

            pair_rows.append({
                "domain":      domain,
                "technique_a": ta,
                "technique_b": tb,
                "statistic":   float(stat),
                "p_raw":       float(pval),
                "n_pairs":     len(merged),
            })

        # Holm correction within this domain.
        p_vals = [r["p_raw"] for r in pair_rows if not np.isnan(r["p_raw"])]
        valid_idx = [i for i, r in enumerate(pair_rows) if not np.isnan(r["p_raw"])]

        if p_vals:
            _, p_holm, _, _ = multipletests(p_vals, method="holm")
            holm_map = dict(zip(valid_idx, p_holm))
        else:
            holm_map = {}

        for i, row in enumerate(pair_rows):
            row["p_holm"]    = float(holm_map.get(i, float("nan")))
            row["reject_holm"] = (
                bool(row["p_holm"] < 0.05)
                if not np.isnan(row.get("p_holm", float("nan")))
                else False
            )
            rows.append(row)

    cols = [
        "domain", "technique_a", "technique_b",
        "n_pairs", "statistic", "p_raw", "p_holm", "reject_holm",
    ]
    return pd.DataFrame(rows)[cols] if rows else pd.DataFrame(columns=cols)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Wilcoxon signed-rank tests between technique pairs across seeds, "
            "per domain, with Holm correction."
        )
    )
    parser.add_argument(
        "--objectives", type=Path, required=True,
        help="CSV file with columns technique, domain, instance, seed, final_objective."
    )
    parser.add_argument(
        "--out", type=Path, required=True,
        help="Output path for the results CSV."
    )
    args = parser.parse_args()

    df = pd.read_csv(args.objectives)
    required = {"technique", "domain", "seed", "final_objective"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {missing}")

    results = wilcoxon_pairwise(df)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out, index=False)
    print(f"Written {len(results)} rows to {args.out}.")

    n_reject = results["reject_holm"].sum()
    print(f"Significant pairs (Holm p < 0.05): {n_reject} / {len(results)}")


if __name__ == "__main__":
    main()
