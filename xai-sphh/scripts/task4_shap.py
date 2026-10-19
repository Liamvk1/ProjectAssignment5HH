#!/usr/bin/env python3
"""Task 4: Per-domain, per-technique, per-seed SHAP analysis.

For each (technique, domain, seed):
  1. Load the trace, build feature matrix and label (accepted)
  2. Exclude feat_llh_count
  3. Train a GradientBoosting surrogate
  4. Report 5-fold CV fidelity (accuracy, ROC-AUC, majority baseline)
  5. Compute SHAP values if ROC-AUC >= 0.6
  6. Compute mean |SHAP| share and rank per feature

Outputs:
  - results/a5/shap/fidelity_report.csv
  - results/a5/shap/shares_and_ranks_per_domain.csv
  - results/a5/shap/stability_kendall_tau.csv
  - results/a5/shap/heatmaps_per_domain.png
"""

import csv
import os
import sys
import warnings
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# Suppress sklearn convergence warnings
warnings.filterwarnings("ignore", category=UserWarning)

TRACES_DIR = Path("results/a5/traces")
OUT_DIR = Path("results/a5/shap")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = ["SAT", "BinPacking", "FlowShop", "TSP", "VRP", "PersonnelScheduling"]
TECHNIQUES = ["SP-SR-LA", "SP-CF-LA", "SP-CF-AILTA", "MP-CF"]
SEEDS_FILE = Path("config/seeds.txt")

# Features to use (exclude feat_llh_count, feat_pop_diversity, feat_pop_target_rank for SP)
FEATURES = [
    "feat_progress", "feat_obj_norm", "feat_gap_to_best",
    "feat_iters_since_improve", "feat_improve_rate_50", "feat_mean_logret_50",
    "feat_last_h1", "feat_last_h2", "feat_last_h3",
    "feat_last_class1", "feat_last_class2", "feat_last_class3",
    "feat_iters_since_accept",
]
MP_EXTRA_FEATURES = ["feat_pop_diversity", "feat_pop_target_rank"]

ROC_AUC_THRESHOLD = 0.6


def load_seeds():
    return [int(s.strip()) for s in SEEDS_FILE.read_text().strip().split("\n")]


def load_trace_features(trace_path, technique):
    """Load trace CSV and return (X, y) feature matrix and labels."""
    df = pd.read_csv(trace_path)

    features = FEATURES.copy()
    if technique.startswith("MP-"):
        features += MP_EXTRA_FEATURES

    # Filter to columns that exist
    available = [f for f in features if f in df.columns]

    X = df[available].copy()
    y = df["accepted"].astype(int).values

    # Handle missing/inf values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(0)

    return X, y, available


def train_and_evaluate(X, y):
    """Train GBM surrogate with 5-fold stratified CV, return metrics."""
    if len(np.unique(y)) < 2:
        return None, None, None, None

    majority = max(np.mean(y), 1 - np.mean(y))

    clf = GradientBoostingClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1,
        random_state=42, subsample=0.8
    )

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    acc_scores = cross_val_score(clf, X, y, cv=skf, scoring="accuracy")
    auc_scores = cross_val_score(clf, X, y, cv=skf, scoring="roc_auc")

    # Train on full data for SHAP
    clf.fit(X, y)

    return clf, np.mean(acc_scores), np.mean(auc_scores), majority


def compute_shap_importance(clf, X, feature_names):
    """Compute mean |SHAP| using TreeSHAP."""
    try:
        import shap
        explainer = shap.TreeExplainer(clf)
        # Sample if dataset is large
        if len(X) > 5000:
            idx = np.random.RandomState(42).choice(len(X), 5000, replace=False)
            X_sample = X.iloc[idx]
        else:
            X_sample = X
        shap_values = explainer.shap_values(X_sample, check_additivity=False)
        # For binary classification, shap_values might be a list of 2 arrays
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # class 1 (accepted)
        mean_abs = np.mean(np.abs(shap_values), axis=0)
        total = mean_abs.sum()
        shares = mean_abs / total if total > 0 else mean_abs
        return dict(zip(feature_names, shares))
    except ImportError:
        # Fallback to feature_importances_ (Gini importance)
        print("WARNING: shap not installed, using feature_importances_", file=sys.stderr)
        imp = clf.feature_importances_
        total = imp.sum()
        shares = imp / total if total > 0 else imp
        return dict(zip(feature_names, shares))


def main():
    seeds = load_seeds()

    fidelity_rows = []
    # domain -> technique -> seed -> {feature: share}
    all_shares = defaultdict(lambda: defaultdict(dict))

    total_surrogates = 0
    flagged = 0

    for domain in DOMAINS:
        for technique in TECHNIQUES:
            for seed in seeds:
                stem = f"{technique}_{domain}_0_{seed}"
                trace_path = TRACES_DIR / f"trace_{stem}.csv"
                if not trace_path.exists():
                    continue

                print(f"Processing {stem}...", end=" ", flush=True)
                X, y, feature_names = load_trace_features(trace_path, technique)

                clf, accuracy, roc_auc, majority = train_and_evaluate(X, y)

                row = {
                    "domain": domain,
                    "technique": technique,
                    "seed": seed,
                    "n_samples": len(y),
                    "accuracy": round(accuracy, 4) if accuracy else None,
                    "roc_auc": round(roc_auc, 4) if roc_auc else None,
                    "majority_baseline": round(majority, 4) if majority else None,
                    "flagged": "",
                }

                total_surrogates += 1

                if roc_auc is not None and roc_auc < ROC_AUC_THRESHOLD:
                    row["flagged"] = "ROC-AUC < 0.6"
                    flagged += 1
                    print(f"FLAGGED (ROC-AUC={roc_auc:.3f})")
                elif clf is not None and roc_auc is not None:
                    shares = compute_shap_importance(clf, X, feature_names)
                    all_shares[domain][technique][seed] = shares
                    print(f"OK (ROC-AUC={roc_auc:.3f})")
                else:
                    row["flagged"] = "training failed"
                    flagged += 1
                    print("FAILED")

                fidelity_rows.append(row)

    # Write fidelity report
    csv_path = OUT_DIR / "fidelity_report.csv"
    fields = ["domain", "technique", "seed", "n_samples", "accuracy",
              "roc_auc", "majority_baseline", "flagged"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(fidelity_rows)
    print(f"\nWritten: {csv_path}")
    print(f"Total surrogates: {total_surrogates}, flagged: {flagged}")

    # Compute aggregate shares and ranks per domain
    share_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            seed_shares = all_shares[domain][technique]
            if not seed_shares:
                continue

            # Get all feature names from first seed
            first = next(iter(seed_shares.values()))
            feature_names = list(first.keys())

            # Mean share across seeds with bootstrap 95% CI
            for feat in feature_names:
                vals = [seed_shares[s].get(feat, 0) for s in seed_shares]
                mean_share = np.mean(vals)
                # Bootstrap 95% CI
                if len(vals) >= 2:
                    boot = []
                    rng = np.random.RandomState(42)
                    for _ in range(1000):
                        sample = rng.choice(vals, len(vals), replace=True)
                        boot.append(np.mean(sample))
                    ci_lo = np.percentile(boot, 2.5)
                    ci_hi = np.percentile(boot, 97.5)
                else:
                    ci_lo = ci_hi = mean_share

                share_rows.append({
                    "domain": domain,
                    "technique": technique,
                    "feature": feat,
                    "mean_share": round(mean_share, 6),
                    "ci_low": round(ci_lo, 6),
                    "ci_high": round(ci_hi, 6),
                    "n_seeds": len(vals),
                })

    # Compute ranks per seed and median rank
    for row in share_rows:
        domain = row["domain"]
        technique = row["technique"]
        feat = row["feature"]
        seed_shares = all_shares[domain][technique]

        per_seed_ranks = []
        for s, shares in seed_shares.items():
            # Rank features by share (1 = most important)
            sorted_feats = sorted(shares.items(), key=lambda x: -x[1])
            for rank_idx, (f, _) in enumerate(sorted_feats, 1):
                if f == feat:
                    per_seed_ranks.append(rank_idx)
                    break
        row["median_rank"] = np.median(per_seed_ranks) if per_seed_ranks else None

    csv_path = OUT_DIR / "shares_and_ranks_per_domain.csv"
    fields = ["domain", "technique", "feature", "mean_share", "ci_low", "ci_high",
              "median_rank", "n_seeds"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(share_rows)
    print(f"Written: {csv_path}")

    # Stability: Kendall's tau between per-seed rankings
    tau_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            seed_shares = all_shares[domain][technique]
            if len(seed_shares) < 2:
                continue

            seed_list = sorted(seed_shares.keys())
            feature_names = list(next(iter(seed_shares.values())).keys())

            # Build ranking per seed
            rankings = {}
            for s in seed_list:
                sorted_feats = sorted(seed_shares[s].items(), key=lambda x: -x[1])
                rank_map = {f: r + 1 for r, (f, _) in enumerate(sorted_feats)}
                rankings[s] = [rank_map[f] for f in feature_names]

            # Pairwise Kendall's tau
            taus = []
            for s1, s2 in combinations(seed_list, 2):
                tau, _ = sp_stats.kendalltau(rankings[s1], rankings[s2])
                taus.append(tau)

            tau_rows.append({
                "domain": domain,
                "technique": technique,
                "mean_kendall_tau": round(np.mean(taus), 4),
                "std_kendall_tau": round(np.std(taus, ddof=1), 4) if len(taus) > 1 else 0,
                "n_pairs": len(taus),
                "n_seeds": len(seed_list),
            })

    csv_path = OUT_DIR / "stability_kendall_tau.csv"
    fields = ["domain", "technique", "mean_kendall_tau", "std_kendall_tau",
              "n_pairs", "n_seeds"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(tau_rows)
    print(f"Written: {csv_path}")

    # Heatmaps: one per domain, features x techniques
    n_domains = len([d for d in DOMAINS if any(all_shares[d][t] for t in TECHNIQUES)])
    if n_domains == 0:
        print("No SHAP data to plot.")
        return

    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    axes = axes.flatten()

    for idx, domain in enumerate(DOMAINS):
        ax = axes[idx]
        # Collect mean shares
        techs_with_data = [t for t in TECHNIQUES if all_shares[domain][t]]
        if not techs_with_data:
            ax.set_visible(False)
            continue

        first_tech = techs_with_data[0]
        feature_names = list(next(iter(all_shares[domain][first_tech].values())).keys())

        matrix = []
        for feat in feature_names:
            row_vals = []
            for technique in techs_with_data:
                seed_shares = all_shares[domain][technique]
                vals = [seed_shares[s].get(feat, 0) for s in seed_shares]
                row_vals.append(np.mean(vals))
            matrix.append(row_vals)

        matrix = np.array(matrix)
        im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
        ax.set_xticks(range(len(techs_with_data)))
        ax.set_xticklabels([t.replace("SP-", "").replace("MP-", "MP-")
                           for t in techs_with_data], rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(feature_names)))
        ax.set_yticklabels([f.replace("feat_", "") for f in feature_names], fontsize=7)
        ax.set_title(domain, fontsize=11, fontweight="bold")

        # Annotate cells
        for i in range(len(feature_names)):
            for j in range(len(techs_with_data)):
                val = matrix[i, j]
                colour = "white" if val > 0.15 else "black"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                       fontsize=6, color=colour)

    plt.suptitle("Mean |SHAP| Share by Feature and Technique (per domain)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig_path = OUT_DIR / "heatmaps_per_domain.png"
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Written: {fig_path}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    main()
