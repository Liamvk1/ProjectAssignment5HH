#!/usr/bin/env python3
"""Phase 1: Effectiveness surrogates (RQ1).

For each domain x technique x seed:
  1. Load trace, build labels (improved, delta_null)
  2. Build feature matrix: pre-application feat_* (excl feat_llh_count)
     + heuristic_class one-hot + heuristic_id (within-domain index)
  3. Train GradientBoosting with class weighting
  4. 5-fold CV grouped by run (one run per fold when single-seed)
  5. Fidelity gate: ROC-AUC >= 0.6, PR-AUC >= 2x positive base rate
  6. SHAP TreeExplainer: global shares, ranks, interactions
  7. LIME: 50 instances over progress, grouped into 10 bands
  8. Effectiveness map: domain x heuristic_class x progress_band
  9. Stability: Kendall's tau across seed pairs

Primary dataset: SP-SR-LA (unconfounded).
Secondary: SP-CF-AILTA, MP-CF (states actually visited).
"""

import csv
import json
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
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, average_precision_score

warnings.filterwarnings("ignore", category=UserWarning)

# --- Configuration ---

TRACES_DIR = Path("results/a5/traces")
OUT_DIR = Path("results/rq1")

DOMAINS = ["SAT", "BinPacking", "FlowShop", "TSP", "VRP", "PersonnelScheduling"]
# Primary: SP-SR-LA (unconfounded); Secondary: SP-CF-AILTA, MP-CF
TECHNIQUES = ["SP-SR-LA", "SP-CF-AILTA", "MP-CF"]
SEEDS = [42, 123, 456, 789, 1024, 2048, 3141, 4242, 5555, 9999]

# Features: all feat_* except feat_llh_count, plus the current heuristic
STATE_FEATURES = [
    "feat_progress", "feat_obj_norm", "feat_gap_to_best",
    "feat_iters_since_improve", "feat_improve_rate_50", "feat_mean_logret_50",
    "feat_last_h1", "feat_last_h2", "feat_last_h3",
    "feat_last_class1", "feat_last_class2", "feat_last_class3",
    "feat_iters_since_accept",
]
MP_FEATURES = ["feat_pop_diversity", "feat_pop_target_rank"]

HEURISTIC_CLASSES = ["MUTATION", "RUIN_RECREATE", "LOCAL_SEARCH", "CROSSOVER"]

ROC_AUC_GATE = 0.6
SHAP_SAMPLE_SIZE = 3000
LIME_GRID_SIZE = 50
LIME_PERTURBATIONS = 1000
N_PROGRESS_BANDS = 10
MAX_TRAIN_ROWS = 30000  # subsample large traces for speed


def load_trace(path):
    df = pd.read_csv(path)
    df["accepted"] = df["accepted"].map({"true": True, "false": False, True: True, False: False}).astype(bool)
    return df


def build_effectiveness_dataset(df, technique):
    """Build X, y for effectiveness prediction.

    Label: improved = 1 if objective_after < objective_before.
    Features: pre-application state + current heuristic (one-hot class + index).
    """
    # Labels
    y_improved = (df["objective_after"] < df["objective_before"]).astype(int).values
    delta_null = (df["objective_after"] == df["objective_before"]).astype(int).values

    # State features
    features = STATE_FEATURES.copy()
    if technique.startswith("MP-"):
        features += MP_FEATURES

    available = [f for f in features if f in df.columns]
    X = df[available].copy()

    # Add current heuristic: one-hot class encoding
    for cls in HEURISTIC_CLASSES:
        X[f"h_is_{cls}"] = (df["heuristic_class"] == cls).astype(int)

    # Add current heuristic index (within-domain, integer)
    X["h_index"] = df["heuristic_id"].values

    # Handle missing/inf
    X = X.replace([np.inf, -np.inf], np.nan).fillna(-1.0)

    feature_names = list(X.columns)

    # Subsample for speed if very large
    if len(X) > MAX_TRAIN_ROWS:
        rng = np.random.RandomState(42)
        idx = rng.choice(len(X), MAX_TRAIN_ROWS, replace=False)
        idx.sort()
        X = X.iloc[idx].reset_index(drop=True)
        y_improved = y_improved[idx]
        delta_null = delta_null[idx]

    return X, y_improved, delta_null, feature_names


def train_and_evaluate(X, y, seed=42):
    """Train GBM with class weighting; return model + fidelity metrics."""
    if len(np.unique(y)) < 2:
        return None, {}

    pos_rate = np.mean(y)
    clf = GradientBoostingClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1,
        subsample=0.8, random_state=seed,
    )

    # Class weighting via sample weights
    weights = np.where(y == 1, 1.0 / max(pos_rate, 1e-6), 1.0 / max(1 - pos_rate, 1e-6))
    weights = weights / weights.mean()

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    roc_scores = []
    pr_scores = []

    for train_idx, test_idx in skf.split(X, y):
        X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        w_tr = weights[train_idx]

        clf_fold = GradientBoostingClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            subsample=0.8, random_state=seed,
        )
        clf_fold.fit(X_tr, y_tr, sample_weight=w_tr)
        y_prob = clf_fold.predict_proba(X_te)[:, 1]
        roc_scores.append(roc_auc_score(y_te, y_prob))
        pr_scores.append(average_precision_score(y_te, y_prob))

    metrics = {
        "roc_auc": np.mean(roc_scores),
        "roc_auc_std": np.std(roc_scores, ddof=1),
        "pr_auc": np.mean(pr_scores),
        "pr_auc_std": np.std(pr_scores, ddof=1),
        "pos_rate": pos_rate,
        "n_samples": len(y),
    }

    # Fidelity gate
    passes_roc = metrics["roc_auc"] >= ROC_AUC_GATE
    passes_pr = metrics["pr_auc"] >= 2 * pos_rate
    metrics["passes_gate"] = passes_roc and passes_pr
    metrics["gate_reason"] = ""
    if not passes_roc:
        metrics["gate_reason"] += f"ROC-AUC={metrics['roc_auc']:.3f}<{ROC_AUC_GATE}; "
    if not passes_pr:
        metrics["gate_reason"] += f"PR-AUC={metrics['pr_auc']:.3f}<2x{pos_rate:.3f}={2*pos_rate:.3f}"

    # Train on full data for SHAP/LIME
    clf.fit(X, y, sample_weight=weights)

    return clf, metrics


def compute_shap(clf, X, feature_names, sample_size=SHAP_SAMPLE_SIZE):
    """Compute SHAP TreeExplainer values. Return shares (abs) and signed means."""
    import shap
    explainer = shap.TreeExplainer(clf)
    if len(X) > sample_size:
        idx = np.random.RandomState(42).choice(len(X), sample_size, replace=False)
        X_sample = X.iloc[idx]
    else:
        X_sample = X
    shap_values = explainer.shap_values(X_sample, check_additivity=False)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    mean_abs = np.mean(np.abs(shap_values), axis=0)
    total = mean_abs.sum()
    shares = mean_abs / total if total > 0 else mean_abs
    # Signed mean SHAP: for h_is_* features, compute conditional on feature=1
    # (i.e., what's the SHAP contribution when this type IS the applied heuristic)
    signed_means = {}
    for i, fname in enumerate(feature_names):
        if fname.startswith("h_is_"):
            # Conditional: mean SHAP only where this type was applied
            mask = X_sample[fname].values == 1
            if mask.sum() > 0:
                signed_means[fname] = float(np.mean(shap_values[mask, i]))
            else:
                signed_means[fname] = 0.0
        else:
            signed_means[fname] = float(np.mean(shap_values[:, i]))
    return (dict(zip(feature_names, shares)),
            signed_means,
            shap_values, X_sample)


def compute_shap_interactions(clf, X, feature_names, sample_size=2000):
    """Compute SHAP interaction values for key feature pairs."""
    import shap
    explainer = shap.TreeExplainer(clf)
    if len(X) > sample_size:
        idx = np.random.RandomState(42).choice(len(X), sample_size, replace=False)
        X_sample = X.iloc[idx]
    else:
        X_sample = X
    interaction_values = explainer.shap_interaction_values(X_sample)
    if isinstance(interaction_values, list):
        interaction_values = interaction_values[1]
    return interaction_values, X_sample


def compute_lime(clf, X, feature_names, n_grid=LIME_GRID_SIZE):
    """LIME explanations at evenly-spaced progress points."""
    from lime.lime_tabular import LimeTabularExplainer

    progress_col = "feat_progress"
    if progress_col not in X.columns:
        return pd.DataFrame()

    progress = X[progress_col].values
    quantiles = np.linspace(0, 1, n_grid + 2)[1:-1]
    thresholds = np.quantile(progress, quantiles)
    indices = [np.argmin(np.abs(progress - t)) for t in thresholds]
    indices = list(dict.fromkeys(indices))  # deduplicate, preserve order

    explainer = LimeTabularExplainer(
        X.values, feature_names=feature_names,
        class_names=["not_improved", "improved"],
        mode="classification", random_state=42,
    )

    rows = []
    for idx in indices:
        prog = progress[idx]
        band = min(int(prog * N_PROGRESS_BANDS), N_PROGRESS_BANDS - 1)
        try:
            exp = explainer.explain_instance(
                X.iloc[idx].values, clf.predict_proba,
                num_features=10, num_samples=LIME_PERTURBATIONS,
            )
            for cond, weight in exp.as_list():
                rows.append({
                    "instance_index": idx,
                    "progress": round(prog, 4),
                    "progress_band": band,
                    "condition": cond,
                    "weight": round(weight, 6),
                    "sign": 1 if weight > 0 else -1,
                })
        except Exception as e:
            print(f"  LIME failed at index {idx}: {e}", file=sys.stderr)

    return pd.DataFrame(rows)


def build_effectiveness_map(df, technique, domain):
    """Model-free effectiveness map: domain x heuristic_class x progress_band."""
    df = df.copy()
    df["improved"] = (df["objective_after"] < df["objective_before"]).astype(int)
    df["progress_band"] = np.clip((df["feat_progress"] * N_PROGRESS_BANDS).astype(int), 0, N_PROGRESS_BANDS - 1)

    rows = []
    for cls in HEURISTIC_CLASSES:
        mask = df["heuristic_class"] == cls
        if mask.sum() == 0:
            continue
        for band in range(N_PROGRESS_BANDS):
            band_mask = mask & (df["progress_band"] == band)
            subset = df[band_mask]
            if len(subset) == 0:
                continue
            rows.append({
                "domain": domain,
                "technique": technique,
                "heuristic_class": cls,
                "progress_band": band,
                "n_applications": len(subset),
                "n_improved": int(subset["improved"].sum()),
                "observed_improvement_rate": round(subset["improved"].mean(), 6),
            })
    return rows


def main():
    os.chdir(Path(__file__).resolve().parent.parent.parent)

    for subdir in ["fidelity", "shap", "lime", "effectiveness_map", "stability", "figures"]:
        (OUT_DIR / subdir).mkdir(parents=True, exist_ok=True)

    fidelity_rows = []
    all_shares = defaultdict(lambda: defaultdict(dict))  # domain -> technique -> seed -> shares
    all_signed = defaultdict(lambda: defaultdict(dict))  # domain -> technique -> seed -> signed means
    all_lime = []
    all_emap = []

    for technique in TECHNIQUES:
        for domain in DOMAINS:
            for seed in SEEDS:
                stem = f"{technique}_{domain}_0_{seed}"
                trace_path = TRACES_DIR / f"trace_{stem}.csv"
                if not trace_path.exists():
                    print(f"SKIP {stem}: file not found")
                    continue

                print(f"Processing {stem}...", end=" ", flush=True)
                df = load_trace(trace_path)
                X, y, delta_null, feature_names = build_effectiveness_dataset(df, technique)

                # Model-free effectiveness map uses FULL trace (before subsampling)
                emap_rows = build_effectiveness_map(df, technique, domain)
                for row in emap_rows:
                    row["seed"] = seed
                all_emap.extend(emap_rows)

                clf, metrics = train_and_evaluate(X, y, seed=seed)
                metrics.update({"domain": domain, "technique": technique, "seed": seed})
                fidelity_rows.append(metrics)

                if not metrics.get("passes_gate", False):
                    reason = metrics.get("gate_reason", "unknown")
                    print(f"FLAGGED ({reason})")
                    continue

                # SHAP
                try:
                    shares, signed_means, shap_vals, X_shap = compute_shap(clf, X, feature_names)
                    all_shares[domain][technique][seed] = shares
                    all_signed[domain][technique][seed] = signed_means
                    print(f"ROC={metrics['roc_auc']:.3f} PR={metrics['pr_auc']:.3f}", end=" ")
                except Exception as e:
                    print(f"SHAP failed: {e}", end=" ")

                # LIME
                try:
                    lime_df = compute_lime(clf, X, feature_names)
                    if not lime_df.empty:
                        lime_df["domain"] = domain
                        lime_df["technique"] = technique
                        lime_df["seed"] = seed
                        all_lime.append(lime_df)
                except Exception as e:
                    print(f"LIME failed: {e}", end=" ")

                print("OK")

    # --- Write fidelity report ---
    fidelity_path = OUT_DIR / "fidelity" / "fidelity_report.csv"
    fidelity_df = pd.DataFrame(fidelity_rows)
    fidelity_df.to_csv(fidelity_path, index=False)
    print(f"\nWritten: {fidelity_path}")

    n_total = len(fidelity_rows)
    n_pass = sum(1 for r in fidelity_rows if r.get("passes_gate", False))
    n_flag = n_total - n_pass
    print(f"Total surrogates: {n_total}, passed: {n_pass}, flagged: {n_flag}")

    # --- Write SHAP shares ---
    share_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            seed_shares = all_shares[domain][technique]
            if not seed_shares:
                continue
            all_feats = list(next(iter(seed_shares.values())).keys())
            for feat in all_feats:
                vals = [seed_shares[s].get(feat, 0) for s in seed_shares]
                share_rows.append({
                    "domain": domain, "technique": technique,
                    "feature": feat,
                    "mean_share": round(np.mean(vals), 6),
                    "std_share": round(np.std(vals, ddof=1), 6) if len(vals) > 1 else 0,
                    "n_seeds": len(vals),
                })
    shares_path = OUT_DIR / "shap" / "shares_and_ranks.csv"
    pd.DataFrame(share_rows).to_csv(shares_path, index=False)
    print(f"Written: {shares_path}")

    # --- Write signed SHAP values per seed (for rule extraction) ---
    signed_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            seed_signed = all_signed[domain][technique]
            for s, svals in seed_signed.items():
                for feat, val in svals.items():
                    signed_rows.append({
                        "domain": domain, "technique": technique, "seed": s,
                        "feature": feat, "signed_shap_mean": round(val, 8),
                    })
    signed_path = OUT_DIR / "shap" / "signed_shap_per_seed.csv"
    pd.DataFrame(signed_rows).to_csv(signed_path, index=False)
    print(f"Written: {signed_path}")

    # --- Build effectiveness map with SHAP contributions ---
    emap_df = pd.DataFrame(all_emap)
    if not emap_df.empty:
        # Aggregate across seeds
        agg = emap_df.groupby(["domain", "technique", "heuristic_class", "progress_band"]).agg(
            n_applications=("n_applications", "sum"),
            n_improved=("n_improved", "sum"),
            observed_improvement_rate=("observed_improvement_rate", "mean"),
            n_seeds=("seed", "nunique"),
        ).reset_index()
        agg["observed_improvement_rate"] = (agg["n_improved"] / agg["n_applications"]).round(6)

        # Add SHAP contribution for each heuristic type
        shap_contribs = []
        for _, row in agg.iterrows():
            domain = row["domain"]
            technique = row["technique"]
            h_cls = row["heuristic_class"]
            feat_name = f"h_is_{h_cls}"

            seed_signed = all_signed[domain][technique]
            # Use signed SHAP means: positive = pushes toward improvement
            contribs = [seed_signed[s].get(feat_name, 0) for s in seed_signed]
            n_negative = sum(1 for c in contribs if c < 0)

            shap_contribs.append({
                "mean_shap_contribution": round(np.mean(contribs), 6) if contribs else 0,
                "n_seeds_negative": n_negative,
                "n_seeds_total": len(contribs),
                "sign_agreement_fraction": round((len(contribs) - n_negative) / len(contribs), 2) if contribs else 0,
            })
        shap_df = pd.DataFrame(shap_contribs)
        agg = pd.concat([agg.reset_index(drop=True), shap_df], axis=1)

        emap_path = OUT_DIR / "effectiveness_map" / "effectiveness_map.csv"
        agg.to_csv(emap_path, index=False)
        print(f"Written: {emap_path}")

    # --- Write LIME ---
    if all_lime:
        lime_combined = pd.concat(all_lime, ignore_index=True)

        # Aggregate: condition frequency by band
        freq = lime_combined.groupby(["domain", "technique", "progress_band", "condition"]).agg(
            count=("weight", "size"),
            mean_weight=("weight", "mean"),
            positive_fraction=("sign", lambda s: (s > 0).mean()),
        ).reset_index()

        lime_path = OUT_DIR / "lime" / "lime_grid.csv"
        lime_combined.to_csv(lime_path, index=False)
        print(f"Written: {lime_path}")

        freq_path = OUT_DIR / "lime" / "condition_frequency.csv"
        freq.to_csv(freq_path, index=False)
        print(f"Written: {freq_path}")

    # --- Stability: Kendall's tau across seed pairs ---
    tau_rows = []
    for domain in DOMAINS:
        for technique in TECHNIQUES:
            seed_shares = all_shares[domain][technique]
            if len(seed_shares) < 2:
                continue
            seed_list = sorted(seed_shares.keys())
            all_feats = list(next(iter(seed_shares.values())).keys())

            rankings = {}
            for s in seed_list:
                sorted_feats = sorted(seed_shares[s].items(), key=lambda x: -x[1])
                rank_map = {f: r + 1 for r, (f, _) in enumerate(sorted_feats)}
                rankings[s] = [rank_map[f] for f in all_feats]

            taus = []
            for s1, s2 in combinations(seed_list, 2):
                tau, _ = sp_stats.kendalltau(rankings[s1], rankings[s2])
                taus.append(tau)

            tau_rows.append({
                "domain": domain, "technique": technique,
                "mean_kendall_tau": round(np.mean(taus), 4),
                "std_kendall_tau": round(np.std(taus, ddof=1), 4) if len(taus) > 1 else 0,
                "n_pairs": len(taus), "n_seeds": len(seed_list),
            })

    tau_path = OUT_DIR / "stability" / "kendall_tau.csv"
    pd.DataFrame(tau_rows).to_csv(tau_path, index=False)
    print(f"Written: {tau_path}")

    print("\n=== Phase 1 complete ===")


if __name__ == "__main__":
    main()
