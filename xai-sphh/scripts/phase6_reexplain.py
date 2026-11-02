#!/usr/bin/env python3
"""Phase 6: Re-explanation (RQ4 mechanism).

1. Retrain effectiveness surrogates on XAI-variant traces.
2. Compare behavioural metrics: masked application fraction, wasted-application
   rate, improvement rate, time-to-median.
3. Compare SHAP shares before (base) vs after (XAI variant).
4. Flag mismatches between behavioural change and performance change.

Focuses on SP-CF-AILTA vs SP-CF-AILTA-XAI (complete data).
"""

import csv
import json
import os
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, average_precision_score

warnings.filterwarnings("ignore", category=UserWarning)

BASE_TRACES = Path("results/a5/traces")
XAI_TRACES = Path("results/rq2/traces")
OUT_DIR = Path("results/rq4_mechanism")
RQ1_DIR = Path("results/rq1")

DOMAINS = ["SAT", "BinPacking", "FlowShop", "TSP", "VRP", "PersonnelScheduling"]
BASE_SEEDS = [42, 123, 456, 789, 1024, 2048, 3141, 4242, 5555, 9999]
XAI_SEEDS = [11, 22, 33, 44, 55, 66, 77, 88, 99, 111]

# Variants to compare
BASE_TECHNIQUE = "SP-CF-AILTA"
XAI_VARIANT = "SP-CF-AILTA-XAI"

STATE_FEATURES = [
    "feat_progress", "feat_obj_norm", "feat_gap_to_best",
    "feat_iters_since_improve", "feat_improve_rate_50", "feat_mean_logret_50",
    "feat_last_h1", "feat_last_h2", "feat_last_h3",
    "feat_last_class1", "feat_last_class2", "feat_last_class3",
    "feat_iters_since_accept",
]
HEURISTIC_CLASSES = ["MUTATION", "RUIN_RECREATE", "LOCAL_SEARCH", "CROSSOVER"]
N_PROGRESS_BANDS = 10
MAX_TRAIN_ROWS = 30000
SHAP_SAMPLE_SIZE = 3000


def load_trace(path):
    df = pd.read_csv(path, low_memory=False)
    df["accepted"] = df["accepted"].map(
        {"true": True, "false": False, True: True, False: False}
    ).astype(bool)
    return df


def load_rules(domain):
    """Load the XAI rules for a domain to know which types are excluded."""
    rules_path = Path(f"rules/{XAI_VARIANT}/{domain}.json")
    if not rules_path.exists():
        return None
    with open(rules_path) as f:
        return json.load(f)


def get_final_objective_from_df(df):
    return df["best_so_far"].iloc[-1]


def compute_behavioural_metrics(df, rules):
    """Compute per-phase behavioural metrics for a trace."""
    df = df.copy()
    df["improved"] = (df["objective_after"] < df["objective_before"]).astype(int)
    df["delta_null"] = (df["objective_after"] == df["objective_before"]).astype(int)
    df["wasted"] = ((df["improved"] == 0) & (df["accepted"] == False)).astype(int)
    df = df.dropna(subset=["feat_progress"])
    df["progress_band"] = np.clip(
        (df["feat_progress"] * N_PROGRESS_BANDS).fillna(0).astype(int), 0, N_PROGRESS_BANDS - 1
    )

    phases = {"early": (0, 2), "middle": (3, 6), "late": (7, 9)}
    metrics = {}

    for phase_name, (lo, hi) in phases.items():
        mask = (df["progress_band"] >= lo) & (df["progress_band"] <= hi)
        subset = df[mask]
        if len(subset) == 0:
            continue

        excluded_types = []
        if rules and "type_class_rules" in rules:
            phase_rules = rules["type_class_rules"].get(phase_name, {})
            excluded_types = phase_rules.get("excluded", [])

        # Fraction of applications on excluded types
        if excluded_types:
            excluded_mask = subset["heuristic_class"].isin(excluded_types)
            excluded_frac = excluded_mask.mean()
        else:
            excluded_frac = 0.0

        metrics[phase_name] = {
            "n_applications": len(subset),
            "improvement_rate": subset["improved"].mean(),
            "delta_null_rate": subset["delta_null"].mean(),
            "wasted_rate": subset["wasted"].mean(),
            "excluded_type_fraction": excluded_frac,
            "excluded_types": ",".join(excluded_types),
        }

    return metrics


def time_to_median(df, target_median):
    """Find the iteration at which best_so_far first reaches or beats the target."""
    below = df["best_so_far"] <= target_median
    if below.any():
        return int(df.loc[below.idxmax(), "iteration"])
    return None  # never reached


def build_features(df):
    """Build feature matrix for surrogate training."""
    features = [f for f in STATE_FEATURES if f in df.columns]
    X = df[features].copy()
    for cls in HEURISTIC_CLASSES:
        X[f"h_is_{cls}"] = (df["heuristic_class"] == cls).astype(int)
    X["h_index"] = df["heuristic_id"].values
    X = X.replace([np.inf, -np.inf], np.nan).fillna(-1.0)

    y = (df["objective_after"] < df["objective_before"]).astype(int).values
    feature_names = list(X.columns)

    if len(X) > MAX_TRAIN_ROWS:
        rng = np.random.RandomState(42)
        idx = rng.choice(len(X), MAX_TRAIN_ROWS, replace=False)
        idx.sort()
        X = X.iloc[idx].reset_index(drop=True)
        y = y[idx]

    return X, y, feature_names


def train_model(X, y, seed=42):
    if len(np.unique(y)) < 2:
        return None, {}
    pos_rate = np.mean(y)
    clf = GradientBoostingClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1,
        subsample=0.8, random_state=seed,
    )
    weights = np.where(y == 1, 1.0 / max(pos_rate, 1e-6), 1.0 / max(1 - pos_rate, 1e-6))
    weights = weights / weights.mean()

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    roc_scores, pr_scores = [], []
    for tr, te in skf.split(X, y):
        m = GradientBoostingClassifier(
            n_estimators=100, max_depth=4, learning_rate=0.1,
            subsample=0.8, random_state=seed,
        )
        m.fit(X.iloc[tr], y[tr], sample_weight=weights[tr])
        yp = m.predict_proba(X.iloc[te])[:, 1]
        roc_scores.append(roc_auc_score(y[te], yp))
        pr_scores.append(average_precision_score(y[te], yp))

    metrics = {
        "roc_auc": np.mean(roc_scores),
        "pr_auc": np.mean(pr_scores),
        "pos_rate": pos_rate,
        "n_samples": len(y),
    }
    clf.fit(X, y, sample_weight=weights)
    return clf, metrics


def compute_shap_signed(clf, X, feature_names):
    import shap
    explainer = shap.TreeExplainer(clf)
    if len(X) > SHAP_SAMPLE_SIZE:
        idx = np.random.RandomState(42).choice(len(X), SHAP_SAMPLE_SIZE, replace=False)
        X_sample = X.iloc[idx]
    else:
        X_sample = X
    shap_values = explainer.shap_values(X_sample, check_additivity=False)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]

    mean_abs = np.mean(np.abs(shap_values), axis=0)
    total = mean_abs.sum()
    shares = dict(zip(feature_names, mean_abs / total if total > 0 else mean_abs))

    signed_means = {}
    for i, fname in enumerate(feature_names):
        if fname.startswith("h_is_"):
            mask = X_sample[fname].values == 1
            if mask.sum() > 0:
                signed_means[fname] = float(np.mean(shap_values[mask, i]))
            else:
                signed_means[fname] = 0.0
        else:
            signed_means[fname] = float(np.mean(shap_values[:, i]))

    return shares, signed_means


def main():
    os.chdir(Path(__file__).resolve().parent.parent)

    for subdir in ["behavioural", "shap_shift", "fidelity"]:
        (OUT_DIR / subdir).mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1. Behavioural metrics comparison
    # =========================================================================
    print("=== Behavioural Metrics ===")
    behav_rows = []

    for domain in DOMAINS:
        rules = load_rules(domain)

        # Base technique medians (from Phase 4 traces on instance 1)
        base_finals = []
        for seed in XAI_SEEDS:
            path = XAI_TRACES / f"trace_{BASE_TECHNIQUE}_{domain}_1_{seed}.csv"
            if path.exists():
                df = load_trace(path)
                base_finals.append(get_final_objective_from_df(df))
        base_median = np.median(base_finals) if base_finals else None

        # Compare base vs XAI for each seed
        for seed in XAI_SEEDS:
            for variant in [BASE_TECHNIQUE, XAI_VARIANT]:
                path = XAI_TRACES / f"trace_{variant}_{domain}_1_{seed}.csv"
                if not path.exists():
                    continue
                df = load_trace(path)
                final_obj = get_final_objective_from_df(df)

                # Phase-level metrics
                phase_metrics = compute_behavioural_metrics(
                    df, rules if variant == XAI_VARIANT else None
                )

                # Time to reach base median
                ttm = time_to_median(df, base_median) if base_median else None

                for phase_name, pm in phase_metrics.items():
                    behav_rows.append({
                        "domain": domain,
                        "variant": variant,
                        "seed": seed,
                        "phase": phase_name,
                        "final_objective": final_obj,
                        "time_to_base_median": ttm,
                        **pm,
                    })

    behav_df = pd.DataFrame(behav_rows)
    behav_path = OUT_DIR / "behavioural" / "per_seed_metrics.csv"
    behav_df.to_csv(behav_path, index=False)
    print(f"Written: {behav_path}")

    # Aggregate summary
    if not behav_df.empty:
        agg = behav_df.groupby(["domain", "variant", "phase"]).agg(
            n_seeds=("seed", "nunique"),
            mean_improvement_rate=("improvement_rate", "mean"),
            mean_wasted_rate=("wasted_rate", "mean"),
            mean_delta_null_rate=("delta_null_rate", "mean"),
            mean_excluded_frac=("excluded_type_fraction", "mean"),
            mean_time_to_median=("time_to_base_median", "mean"),
        ).reset_index()
        agg_path = OUT_DIR / "behavioural" / "aggregate_metrics.csv"
        agg.to_csv(agg_path, index=False)
        print(f"Written: {agg_path}")

        # Print summary
        for domain in DOMAINS:
            print(f"\n  {domain}:")
            dsub = agg[agg["domain"] == domain]
            for _, row in dsub.iterrows():
                print(f"    {row['variant']:30s} {row['phase']:8s}  "
                      f"impr={row['mean_improvement_rate']:.4f}  "
                      f"wasted={row['mean_wasted_rate']:.4f}  "
                      f"excl_frac={row['mean_excluded_frac']:.4f}")

    # =========================================================================
    # 2. Retrain surrogates on XAI variant traces + SHAP comparison
    # =========================================================================
    print("\n=== SHAP Shift Analysis ===")
    fidelity_rows = []
    shap_shift_rows = []

    # Load Phase 1 signed SHAP for comparison
    phase1_signed = defaultdict(dict)
    signed_path = RQ1_DIR / "shap" / "signed_shap_per_seed.csv"
    if signed_path.exists():
        sdf = pd.read_csv(signed_path)
        # Use SP-SR-LA as the reference (unconfounded)
        sr = sdf[sdf["technique"] == "SP-SR-LA"]
        for domain in DOMAINS:
            dsub = sr[sr["domain"] == domain]
            for feat in dsub["feature"].unique():
                vals = dsub[dsub["feature"] == feat]["signed_shap_mean"].values
                phase1_signed[domain][feat] = float(np.mean(vals))

    for domain in DOMAINS:
        rules = load_rules(domain)
        excluded_by_phase = {}
        if rules and "type_class_rules" in rules:
            for ph in ["early", "middle", "late"]:
                excluded_by_phase[ph] = rules["type_class_rules"].get(ph, {}).get("excluded", [])

        xai_signed_all = defaultdict(list)

        for seed in XAI_SEEDS:
            path = XAI_TRACES / f"trace_{XAI_VARIANT}_{domain}_1_{seed}.csv"
            if not path.exists():
                continue

            df = load_trace(path)
            X, y, feature_names = build_features(df)

            clf, metrics = train_model(X, y, seed=seed)
            metrics["domain"] = domain
            metrics["variant"] = XAI_VARIANT
            metrics["seed"] = seed
            fidelity_rows.append(metrics)

            if clf is None:
                print(f"  {domain} seed {seed}: model failed")
                continue

            print(f"  {domain} seed {seed}: ROC={metrics['roc_auc']:.3f} "
                  f"PR={metrics['pr_auc']:.3f}", flush=True)

            shares, signed = compute_shap_signed(clf, X, feature_names)
            for feat, val in signed.items():
                xai_signed_all[feat].append(val)

        # Compare SHAP shift for heuristic type features
        for cls in HEURISTIC_CLASSES:
            feat = f"h_is_{cls}"
            phase1_val = phase1_signed.get(domain, {}).get(feat, 0)
            xai_vals = xai_signed_all.get(feat, [])
            xai_mean = np.mean(xai_vals) if xai_vals else 0

            is_excluded = any(
                cls in excluded_by_phase.get(ph, [])
                for ph in ["early", "middle", "late"]
            )

            shap_shift_rows.append({
                "domain": domain,
                "heuristic_class": cls,
                "phase1_signed_shap": round(phase1_val, 6),
                "xai_variant_signed_shap": round(xai_mean, 6),
                "shap_shift": round(xai_mean - phase1_val, 6),
                "was_excluded": is_excluded,
                "n_xai_seeds": len(xai_vals),
            })

    # Write fidelity
    fid_path = OUT_DIR / "fidelity" / "xai_variant_fidelity.csv"
    pd.DataFrame(fidelity_rows).to_csv(fid_path, index=False)
    print(f"\nWritten: {fid_path}")

    # Write SHAP shift
    shift_df = pd.DataFrame(shap_shift_rows)
    shift_path = OUT_DIR / "shap_shift" / "shap_shift.csv"
    shift_df.to_csv(shift_path, index=False)
    print(f"Written: {shift_path}")

    # =========================================================================
    # 3. Mismatch detection
    # =========================================================================
    print("\n=== Mismatch Detection ===")

    # Load Phase 5 results to know which domains improved
    wilcoxon_path = Path("results/rq2/statistics/wilcoxon_tests.csv")
    perf_improved = {}
    if wilcoxon_path.exists():
        wdf = pd.read_csv(wilcoxon_path)
        xai_base = wdf[(wdf["comparison"] == "XAI vs BASE") &
                        (wdf["base_technique"] == BASE_TECHNIQUE)]
        for _, row in xai_base.iterrows():
            # A12 < 0.5 means XAI is better (lower objective)
            perf_improved[row["domain"]] = {
                "a12": row["a12"],
                "significant": row["significant"],
                "xai_better": row["a12"] < 0.5,
            }

    mismatch_rows = []
    for domain in DOMAINS:
        perf = perf_improved.get(domain, {})
        xai_better = perf.get("xai_better", False)
        significant = perf.get("significant", "no") == "yes"

        # Check if behaviour changed as predicted
        domain_shifts = shift_df[shift_df["domain"] == domain]
        excluded_shifts = domain_shifts[domain_shifts["was_excluded"]]

        # Behaviour changed = excluded types have reduced SHAP
        behaviour_changed = False
        if not excluded_shifts.empty:
            mean_shift = excluded_shifts["shap_shift"].mean()
            behaviour_changed = mean_shift < 0  # negative shift = less positive SHAP

        mismatch_type = "none"
        if xai_better and not behaviour_changed:
            mismatch_type = "performance_without_behaviour"
        elif behaviour_changed and not xai_better:
            mismatch_type = "behaviour_without_performance"

        mismatch_rows.append({
            "domain": domain,
            "xai_better": xai_better,
            "significant": significant,
            "behaviour_changed": behaviour_changed,
            "mismatch_type": mismatch_type,
            "a12": perf.get("a12", None),
        })

        flag = " *** MISMATCH" if mismatch_type != "none" else ""
        print(f"  {domain:25s}  perf_better={xai_better}  "
              f"sig={significant}  behav_changed={behaviour_changed}{flag}")

    mismatch_path = OUT_DIR / "behavioural" / "mismatch_flags.csv"
    pd.DataFrame(mismatch_rows).to_csv(mismatch_path, index=False)
    print(f"\nWritten: {mismatch_path}")

    print("\n=== Phase 6 complete ===")


if __name__ == "__main__":
    main()
