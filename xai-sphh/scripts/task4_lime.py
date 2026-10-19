#!/usr/bin/env python3
"""Task 4b: Per-domain, per-technique, per-seed LIME grid analysis.

Uses the same grid-based approach as Assessment 4's lime_grid module:
explains instances at evenly-spaced progress points across the search budget,
recording each LIME condition with its sign (positive = pushes toward acceptance)
and weight. This identifies which feature conditions most frequently drive
acceptance at different stages of the search.

For each (technique, domain, seed):
  1. Load trace, build feature matrix and label (accepted)
  2. Exclude feat_llh_count
  3. Train a GradientBoosting surrogate (same as SHAP script)
  4. Skip if ROC-AUC < 0.6 (same fidelity gate)
  5. Explain n_grid evenly-spaced instances across feat_progress
  6. Record conditions, signs, weights by progress band (10 bands)
  7. Aggregate: condition frequency, positive_fraction, mean weight per band

Outputs:
  - results/a5/lime/fidelity_report.csv
  - results/a5/lime/condition_frequency_by_band.csv   (conditions x bands x techniques)
  - results/a5/lime/acceptance_drivers.csv             (top conditions driving acceptance)
  - results/a5/lime/feature_shares_per_domain.csv      (mean |weight| shares, comparable to SHAP)
  - results/a5/lime/stability_kendall_tau.csv
  - results/a5/lime/heatmaps_per_domain.png
"""

import csv
import os
import sys
import warnings
from collections import defaultdict, Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", category=UserWarning)

TRACES_DIR = Path("results/a5/traces")
OUT_DIR = Path("results/a5/lime")
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = ["SAT", "BinPacking", "FlowShop", "TSP", "VRP", "PersonnelScheduling"]
TECHNIQUES = ["SP-SR-LA", "SP-CF-LA", "SP-CF-AILTA", "MP-CF"]
SEEDS_FILE = Path("config/seeds.txt")

FEATURES = [
    "feat_progress", "feat_obj_norm", "feat_gap_to_best",
    "feat_iters_since_improve", "feat_improve_rate_50", "feat_mean_logret_50",
    "feat_last_h1", "feat_last_h2", "feat_last_h3",
    "feat_last_class1", "feat_last_class2", "feat_last_class3",
    "feat_iters_since_accept",
]
MP_EXTRA_FEATURES = ["feat_pop_diversity", "feat_pop_target_rank"]

ROC_AUC_THRESHOLD = 0.6
N_GRID = 50           # instances to explain per run (evenly spaced by progress)
LIME_NUM_FEATURES = 10
LIME_NUM_SAMPLES = 5000
N_BANDS = 10          # progress bands [0-10%, 10-20%, ..., 90-100%]


def load_seeds():
    return [int(s.strip()) for s in SEEDS_FILE.read_text().strip().split("\n")]


def load_trace_features(trace_path, technique):
    df = pd.read_csv(trace_path)
    features = FEATURES.copy()
    if technique.startswith("MP-"):
        features += MP_EXTRA_FEATURES
    available = [f for f in features if f in df.columns]
    X = df[available].copy()
    y = df["accepted"].astype(int).values
    progress = df["feat_progress"] if "feat_progress" in df.columns else pd.Series(np.linspace(0, 1, len(df)))
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(0)
    return X, y, available, progress


def train_and_evaluate(X, y):
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
    clf.fit(X, y)
    return clf, np.mean(acc_scores), np.mean(auc_scores), majority


def lime_grid_explain(clf, X, feature_names, progress, seed):
    """Explain n_grid evenly-spaced instances across feat_progress.

    Returns a list of records, each with:
      instance_index, progress, progress_band, condition, feature, sign, weight
    Also returns per-feature mean |weight| shares for comparison with SHAP.
    """
    import lime.lime_tabular

    X_array = X.values
    progress_vals = progress.values

    explainer = lime.lime_tabular.LimeTabularExplainer(
        training_data=X_array,
        feature_names=feature_names,
        class_names=["rejected", "accepted"],
        mode="classification",
        discretize_continuous=True,
        random_state=seed,
    )

    # Select grid points: evenly spaced by progress quantiles
    sorted_idx = np.argsort(progress_vals)
    quantile_positions = np.linspace(0, len(sorted_idx) - 1, N_GRID, dtype=int)
    grid_indices = sorted_idx[quantile_positions]

    band_edges = np.linspace(0.0, 1.0, N_BANDS + 1)

    records = []
    feat_weights = defaultdict(list)  # for computing shares

    for idx in grid_indices:
        instance = X_array[idx]
        prog_val = float(progress_vals[idx])

        try:
            exp = explainer.explain_instance(
                data_row=instance,
                predict_fn=clf.predict_proba,
                num_features=LIME_NUM_FEATURES,
                num_samples=LIME_NUM_SAMPLES,
            )
        except Exception:
            continue

        band = int(np.searchsorted(band_edges, prog_val, side="right") - 1)
        band = min(band, N_BANDS - 1)

        for condition, weight in exp.as_list():
            sign = 1 if weight > 0 else -1

            # Map condition back to feature name
            matched_feat = None
            for feat in feature_names:
                if feat in condition:
                    matched_feat = feat
                    break

            records.append({
                "instance_index": int(idx),
                "progress": prog_val,
                "progress_band": band,
                "condition": str(condition),
                "feature": matched_feat,
                "sign": sign,
                "weight": float(weight),
            })

            if matched_feat:
                feat_weights[matched_feat].append(abs(weight))

    # Compute mean |weight| shares (comparable to SHAP shares)
    mean_weights = {}
    for feat in feature_names:
        if feat in feat_weights:
            mean_weights[feat] = np.mean(feat_weights[feat])
        else:
            mean_weights[feat] = 0.0
    total = sum(mean_weights.values())
    shares = {f: v / total if total > 0 else 0 for f, v in mean_weights.items()}

    return records, shares


def main():
    seeds = load_seeds()

    fidelity_rows = []
    all_shares = defaultdict(lambda: defaultdict(dict))       # domain -> tech -> seed -> {feat: share}
    all_records = defaultdict(lambda: defaultdict(list))       # domain -> tech -> [records]

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
                X, y, feature_names, progress = load_trace_features(trace_path, technique)
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
                    records, shares = lime_grid_explain(clf, X, feature_names, progress, seed)
                    all_shares[domain][technique][seed] = shares
                    all_records[domain][technique].extend(records)
                    print(f"OK (ROC-AUC={roc_auc:.3f})")
                else:
                    row["flagged"] = "training failed"
                    flagged += 1
                    print("FAILED")

                fidelity_rows.append(row)

    # --- Write fidelity report ---
    csv_path = OUT_DIR / "fidelity_report.csv"
    fields = ["domain", "technique", "seed", "n_samples", "accuracy",
              "roc_auc", "majority_baseline", "flagged"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(fidelity_rows)
    print(f"\nWritten: {csv_path}")
    print(f"Total surrogates: {total_surrogates}, flagged: {flagged}")

    # --- Condition frequency by progress band (the key LIME output) ---
    # Aggregates across all seeds: for each (domain, technique, band, condition),
    # reports count, mean_weight, positive_fraction (how often it drives acceptance)
    cond_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            records = all_records[domain][technique]
            if not records:
                continue
            df_rec = pd.DataFrame(records)
            agg = (
                df_rec.groupby(["progress_band", "condition"])
                .agg(
                    count=("weight", "count"),
                    mean_weight=("weight", "mean"),
                    mean_abs_weight=("weight", lambda w: np.mean(np.abs(w))),
                    positive_fraction=("sign", lambda s: (s == 1).mean()),
                )
                .reset_index()
                .sort_values(["progress_band", "count"], ascending=[True, False])
            )
            for _, r in agg.iterrows():
                cond_rows.append({
                    "domain": domain,
                    "technique": technique,
                    "progress_band": int(r["progress_band"]),
                    "condition": r["condition"],
                    "count": int(r["count"]),
                    "mean_weight": round(float(r["mean_weight"]), 6),
                    "mean_abs_weight": round(float(r["mean_abs_weight"]), 6),
                    "positive_fraction": round(float(r["positive_fraction"]), 4),
                })

    csv_path = OUT_DIR / "condition_frequency_by_band.csv"
    fields = ["domain", "technique", "progress_band", "condition", "count",
              "mean_weight", "mean_abs_weight", "positive_fraction"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(cond_rows)
    print(f"Written: {csv_path}")

    # --- Acceptance drivers: top conditions with positive_fraction > 0.5 ---
    # These are the conditions that most frequently push toward acceptance
    driver_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            records = all_records[domain][technique]
            if not records:
                continue
            df_rec = pd.DataFrame(records)
            # Aggregate across all bands
            agg = (
                df_rec.groupby("condition")
                .agg(
                    count=("weight", "count"),
                    mean_weight=("weight", "mean"),
                    mean_abs_weight=("weight", lambda w: np.mean(np.abs(w))),
                    positive_fraction=("sign", lambda s: (s == 1).mean()),
                    feature=("feature", "first"),
                )
                .reset_index()
                .sort_values("count", ascending=False)
            )
            # Top 20 conditions that push toward acceptance (positive_fraction > 0.5)
            accept_drivers = agg[agg["positive_fraction"] > 0.5].head(20)
            for _, r in accept_drivers.iterrows():
                driver_rows.append({
                    "domain": domain,
                    "technique": technique,
                    "condition": r["condition"],
                    "feature": r["feature"],
                    "count": int(r["count"]),
                    "mean_weight": round(float(r["mean_weight"]), 6),
                    "positive_fraction": round(float(r["positive_fraction"]), 4),
                })

    csv_path = OUT_DIR / "acceptance_drivers.csv"
    fields = ["domain", "technique", "condition", "feature", "count",
              "mean_weight", "positive_fraction"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(driver_rows)
    print(f"Written: {csv_path}")

    # --- Feature shares per domain (comparable to SHAP shares) ---
    share_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            seed_shares = all_shares[domain][technique]
            if not seed_shares:
                continue
            first = next(iter(seed_shares.values()))
            feature_names = list(first.keys())

            for feat in feature_names:
                vals = [seed_shares[s].get(feat, 0) for s in seed_shares]
                mean_share = np.mean(vals)
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
            sorted_feats = sorted(shares.items(), key=lambda x: -x[1])
            for rank_idx, (f, _) in enumerate(sorted_feats, 1):
                if f == feat:
                    per_seed_ranks.append(rank_idx)
                    break
        row["median_rank"] = np.median(per_seed_ranks) if per_seed_ranks else None

    csv_path = OUT_DIR / "feature_shares_per_domain.csv"
    fields = ["domain", "technique", "feature", "mean_share", "ci_low", "ci_high",
              "median_rank", "n_seeds"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(share_rows)
    print(f"Written: {csv_path}")

    # --- Stability: Kendall's tau between per-seed rankings ---
    tau_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            seed_shares = all_shares[domain][technique]
            if len(seed_shares) < 2:
                continue
            seed_list = sorted(seed_shares.keys())
            feature_names = list(next(iter(seed_shares.values())).keys())
            rankings = {}
            for s in seed_list:
                sorted_feats = sorted(seed_shares[s].items(), key=lambda x: -x[1])
                rank_map = {f: r + 1 for r, (f, _) in enumerate(sorted_feats)}
                rankings[s] = [rank_map[f] for f in feature_names]
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

    # --- Heatmaps: one per domain, features x techniques ---
    n_domains = len([d for d in DOMAINS if any(all_shares[d][t] for t in TECHNIQUES)])
    if n_domains == 0:
        print("No LIME data to plot.")
        return

    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    axes = axes.flatten()

    for idx, domain in enumerate(DOMAINS):
        ax = axes[idx]
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
        ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
        ax.set_xticks(range(len(techs_with_data)))
        ax.set_xticklabels([t.replace("SP-", "").replace("MP-", "MP-")
                           for t in techs_with_data], rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(feature_names)))
        ax.set_yticklabels([f.replace("feat_", "") for f in feature_names], fontsize=7)
        ax.set_title(domain, fontsize=11, fontweight="bold")

        for i in range(len(feature_names)):
            for j in range(len(techs_with_data)):
                val = matrix[i, j]
                colour = "white" if val > 0.15 else "black"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                       fontsize=6, color=colour)

    plt.suptitle("Mean |LIME weight| Share by Feature and Technique (per domain)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig_path = OUT_DIR / "heatmaps_per_domain.png"
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Written: {fig_path}")


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    main()
