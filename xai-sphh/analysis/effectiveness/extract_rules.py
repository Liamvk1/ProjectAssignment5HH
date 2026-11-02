#!/usr/bin/env python3
"""Phase 2: Fixed rule-extraction procedure.

Reads the effectiveness map and SHAP shares from Phase 1.
Produces machine-readable rules files for the Java variants.

Rule A (selection mask):
  - Divide run into 3 phases: early (bands 0-2), middle (3-6), late (7-9)
  - A heuristic type class is EXCLUDED in a phase if:
    (a) its mean SHAP contribution to improvement is negative in >= 8/10 seeds
    (b) its observed improvement rate < half the domain-phase mean
    (c) at least one type class remains allowed
  - Produces both type-class-level and heuristic-level rules

Rule B (optional):
  - Reheat trigger for SP-CF-AILTA if stagnation LIME condition has tau >= 0.5
  - Diversity trigger for MP-CF if pop_diversity LIME condition has tau >= 0.5
  - Skipped if conditions not met (logged)

Output: rules/<variant>/<domain>.json
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --- Configuration ---

EFFECTIVENESS_MAP_PATH = Path("results/rq1/effectiveness_map/effectiveness_map.csv")
SHAP_SHARES_PATH = Path("results/rq1/shap/shares_and_ranks.csv")
LIME_FREQ_PATH = Path("results/rq1/lime/condition_frequency.csv")
STABILITY_PATH = Path("results/rq1/stability/kendall_tau.csv")
TRACES_DIR = Path("results/a5/traces")

RULES_DIR = Path("rules")

DOMAINS = ["SAT", "BinPacking", "FlowShop", "TSP", "VRP", "PersonnelScheduling"]
HEURISTIC_CLASSES = ["MUTATION", "RUIN_RECREATE", "LOCAL_SEARCH", "CROSSOVER"]
SEEDS = [42, 123, 456, 789, 1024, 2048, 3141, 4242, 5555, 9999]

# Phase boundaries (inclusive band ranges)
PHASES = {
    "early": (0, 2),
    "middle": (3, 6),
    "late": (7, 9),
}

# Exclusion thresholds
MIN_NEGATIVE_SEEDS = 8   # (a) SHAP contribution negative in >= 8/10 seeds
RATE_FRACTION = 0.5      # (b) improvement rate < 0.5 * domain-phase mean
LIME_TAU_THRESHOLD = 0.5 # Rule B: stability threshold


def load_per_seed_shap_contributions(traces_dir, domain, technique, seeds):
    """Compute per-seed SHAP-like contribution from effectiveness map raw data.

    For Rule A condition (a), we need the sign of the SHAP contribution per seed.
    We approximate this from the per-seed effectiveness map rows.
    """
    # This is built during Phase 1 — here we read the per-seed effectiveness map
    # from the raw effectiveness_map.csv (which has per-seed rows before aggregation)
    # Actually the aggregated map doesn't have per-seed SHAP. We need to reconstruct.
    # For now, use the SHAP shares per seed from the build_surrogates output.
    pass


def load_effectiveness_map():
    df = pd.read_csv(EFFECTIVENESS_MAP_PATH)
    return df


def extract_rule_a_for_domain(emap_df, domain, technique):
    """Extract Rule A selection mask for a single domain-technique pair.

    Returns dict: phase -> list of excluded heuristic classes.
    """
    ddf = emap_df[(emap_df["domain"] == domain) & (emap_df["technique"] == technique)]
    if ddf.empty:
        return {}

    rules = {}
    for phase_name, (band_lo, band_hi) in PHASES.items():
        phase_df = ddf[(ddf["progress_band"] >= band_lo) & (ddf["progress_band"] <= band_hi)]
        if phase_df.empty:
            rules[phase_name] = {"excluded": [], "allowed": HEURISTIC_CLASSES[:]}
            continue

        # Domain-phase mean improvement rate
        total_apps = phase_df["n_applications"].sum()
        total_improved = phase_df["n_improved"].sum()
        domain_phase_mean = total_improved / total_apps if total_apps > 0 else 0

        excluded = []
        for cls in HEURISTIC_CLASSES:
            cls_rows = phase_df[phase_df["heuristic_class"] == cls]
            if cls_rows.empty:
                continue

            # Condition (a): SHAP contribution negative in >= 8/10 seeds
            # Use sign_agreement_fraction: fraction of seeds where SHAP > 0
            # If sign_agreement_fraction < 0.2, then >= 8/10 seeds had negative SHAP
            sign_agree = cls_rows["sign_agreement_fraction"].mean()
            cond_a = sign_agree <= (1 - MIN_NEGATIVE_SEEDS / 10)

            # Condition (b): observed improvement rate < half domain-phase mean
            cls_rate = cls_rows["observed_improvement_rate"].mean()
            cond_b = cls_rate < RATE_FRACTION * domain_phase_mean

            if cond_a and cond_b:
                excluded.append(cls)

        # Condition (c): at least one type class must remain
        allowed = [c for c in HEURISTIC_CLASSES if c not in excluded]
        if not allowed:
            # Keep the class with the highest improvement rate
            best_cls = None
            best_rate = -1
            for cls in excluded:
                cls_rows = phase_df[phase_df["heuristic_class"] == cls]
                if not cls_rows.empty:
                    rate = cls_rows["observed_improvement_rate"].mean()
                    if rate > best_rate:
                        best_rate = rate
                        best_cls = cls
            if best_cls:
                excluded.remove(best_cls)
                allowed = [best_cls]

        rules[phase_name] = {
            "excluded": sorted(excluded),
            "allowed": sorted([c for c in HEURISTIC_CLASSES if c not in excluded]),
            "domain_phase_mean_rate": round(domain_phase_mean, 6),
        }

    return rules


def build_heuristic_level_rules(emap_df, domain, technique, type_class_rules, traces_dir):
    """Map type-class exclusions to specific heuristic indices using the domain's type mapping."""
    # Read one trace to get heuristic_id -> heuristic_class mapping
    for seed in SEEDS:
        trace_path = traces_dir / f"trace_{technique}_{domain}_0_{seed}.csv"
        if trace_path.exists():
            df = pd.read_csv(trace_path, usecols=["heuristic_id", "heuristic_class"], nrows=10000)
            h_map = df.groupby("heuristic_id")["heuristic_class"].first().to_dict()
            break
    else:
        return {}

    h_rules = {}
    for phase_name, rule in type_class_rules.items():
        excluded_classes = set(rule["excluded"])
        excluded_h = [h for h, cls in h_map.items() if cls in excluded_classes]
        allowed_h = [h for h, cls in h_map.items() if cls not in excluded_classes]
        h_rules[phase_name] = {
            "excluded_heuristics": sorted(excluded_h),
            "allowed_heuristics": sorted(allowed_h),
        }

    return h_rules


def build_lodo_rules(emap_df, held_out_domain, technique):
    """Leave-one-domain-out: aggregate type-class rules from other 5 domains."""
    other_domains = [d for d in DOMAINS if d != held_out_domain]

    # For each phase and class, vote across domains
    phase_votes = {}
    for phase_name, (band_lo, band_hi) in PHASES.items():
        class_exclude_votes = {cls: 0 for cls in HEURISTIC_CLASSES}
        class_total_votes = {cls: 0 for cls in HEURISTIC_CLASSES}

        for domain in other_domains:
            ddf = emap_df[(emap_df["domain"] == domain) & (emap_df["technique"] == technique)]
            phase_df = ddf[(ddf["progress_band"] >= band_lo) & (ddf["progress_band"] <= band_hi)]
            if phase_df.empty:
                continue

            total_apps = phase_df["n_applications"].sum()
            total_improved = phase_df["n_improved"].sum()
            domain_phase_mean = total_improved / total_apps if total_apps > 0 else 0

            for cls in HEURISTIC_CLASSES:
                cls_rows = phase_df[phase_df["heuristic_class"] == cls]
                if cls_rows.empty:
                    continue
                class_total_votes[cls] += 1

                sign_agree = cls_rows["sign_agreement_fraction"].mean()
                cond_a = sign_agree <= (1 - MIN_NEGATIVE_SEEDS / 10)
                cls_rate = cls_rows["observed_improvement_rate"].mean()
                cond_b = cls_rate < RATE_FRACTION * domain_phase_mean

                if cond_a and cond_b:
                    class_exclude_votes[cls] += 1

        # Majority vote: exclude if > half of other domains exclude it
        excluded = []
        for cls in HEURISTIC_CLASSES:
            total = class_total_votes[cls]
            if total > 0 and class_exclude_votes[cls] > total / 2:
                excluded.append(cls)

        allowed = [c for c in HEURISTIC_CLASSES if c not in excluded]
        if not allowed:
            # Keep the one with fewest exclude votes
            least_excluded = min(HEURISTIC_CLASSES, key=lambda c: class_exclude_votes.get(c, 0))
            excluded.remove(least_excluded)
            allowed = [least_excluded]

        phase_votes[phase_name] = {
            "excluded": sorted(excluded),
            "allowed": sorted([c for c in HEURISTIC_CLASSES if c not in excluded]),
            "vote_counts": {cls: class_exclude_votes[cls] for cls in HEURISTIC_CLASSES},
        }

    return phase_votes


def build_random_mask(type_class_rules, domain, rng_seed=12345):
    """Control: random mask with same exclusion count per phase."""
    rng = np.random.RandomState(rng_seed)
    random_rules = {}
    for phase_name, rule in type_class_rules.items():
        n_exclude = len(rule["excluded"])
        if n_exclude == 0 or n_exclude >= len(HEURISTIC_CLASSES):
            random_rules[phase_name] = {
                "excluded": rule["excluded"][:],
                "allowed": rule["allowed"][:],
            }
            continue
        # Random choice of n_exclude classes
        shuffled = rng.permutation(HEURISTIC_CLASSES).tolist()
        excluded = sorted(shuffled[:n_exclude])
        allowed = sorted(shuffled[n_exclude:])
        random_rules[phase_name] = {"excluded": excluded, "allowed": allowed}
    return random_rules


def build_stat_mask(emap_df, domain, technique):
    """Control: mask built from mean clipped log return per type and phase (no surrogate)."""
    ddf = emap_df[(emap_df["domain"] == domain) & (emap_df["technique"] == technique)]
    if ddf.empty:
        return {}

    stat_rules = {}
    for phase_name, (band_lo, band_hi) in PHASES.items():
        phase_df = ddf[(ddf["progress_band"] >= band_lo) & (ddf["progress_band"] <= band_hi)]
        if phase_df.empty:
            stat_rules[phase_name] = {"excluded": [], "allowed": HEURISTIC_CLASSES[:]}
            continue

        total_apps = phase_df["n_applications"].sum()
        total_improved = phase_df["n_improved"].sum()
        domain_phase_mean = total_improved / total_apps if total_apps > 0 else 0

        # Use purely observed improvement rate (no SHAP at all)
        excluded = []
        for cls in HEURISTIC_CLASSES:
            cls_rows = phase_df[phase_df["heuristic_class"] == cls]
            if cls_rows.empty:
                continue
            cls_rate = cls_rows["observed_improvement_rate"].mean()
            # Exclude if below half the mean (same threshold, but no SHAP condition)
            if cls_rate < RATE_FRACTION * domain_phase_mean:
                excluded.append(cls)

        allowed = [c for c in HEURISTIC_CLASSES if c not in excluded]
        if not allowed:
            best_cls = max(HEURISTIC_CLASSES,
                           key=lambda c: phase_df[phase_df["heuristic_class"] == c]["observed_improvement_rate"].mean()
                           if not phase_df[phase_df["heuristic_class"] == c].empty else 0)
            excluded.remove(best_cls)
            allowed = [best_cls]

        stat_rules[phase_name] = {"excluded": sorted(excluded), "allowed": sorted(allowed)}

    return stat_rules


def check_rule_b(lime_freq_path, stability_path):
    """Check whether Rule B conditions are met."""
    result = {"sp_reheat": False, "mp_diversity": False, "reasons": []}

    if not lime_freq_path.exists() or not stability_path.exists():
        result["reasons"].append("LIME or stability files not found")
        return result

    tau_df = pd.read_csv(stability_path)
    lime_df = pd.read_csv(lime_freq_path)

    # SP-CF-AILTA: check for stagnation LIME condition with tau >= 0.5
    sp_tau = tau_df[(tau_df["technique"] == "SP-CF-AILTA")]
    if not sp_tau.empty:
        mean_tau = sp_tau["mean_kendall_tau"].mean()
        if mean_tau >= LIME_TAU_THRESHOLD:
            stag_conds = lime_df[
                (lime_df["technique"] == "SP-CF-AILTA") &
                (lime_df["condition"].str.contains("iters_since_improve", na=False))
            ]
            if not stag_conds.empty:
                result["sp_reheat"] = True
                result["sp_threshold"] = float(stag_conds.iloc[0]["condition"].split()[-1])
            else:
                result["reasons"].append("No stagnation LIME condition found for SP-CF-AILTA")
        else:
            result["reasons"].append(f"SP-CF-AILTA tau={mean_tau:.3f} < {LIME_TAU_THRESHOLD}")

    # MP-CF: check for diversity LIME condition with tau >= 0.5
    mp_tau = tau_df[(tau_df["technique"] == "MP-CF")]
    if not mp_tau.empty:
        mean_tau = mp_tau["mean_kendall_tau"].mean()
        if mean_tau >= LIME_TAU_THRESHOLD:
            div_conds = lime_df[
                (lime_df["technique"] == "MP-CF") &
                (lime_df["condition"].str.contains("pop_diversity", na=False))
            ]
            if not div_conds.empty:
                result["mp_diversity"] = True
                result["mp_threshold"] = float(div_conds.iloc[0]["condition"].split()[-1])
            else:
                result["reasons"].append("No diversity LIME condition found for MP-CF")
        else:
            result["reasons"].append(f"MP-CF tau={mean_tau:.3f} < {LIME_TAU_THRESHOLD}")

    return result


def write_rules(rules_dict, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(rules_dict, f, indent=2, sort_keys=True)


def main():
    os.chdir(Path(__file__).resolve().parent.parent.parent)

    print("=== Phase 2: Rule Extraction ===\n")

    emap_df = load_effectiveness_map()
    print(f"Loaded effectiveness map: {len(emap_df)} rows")

    rule_b = check_rule_b(LIME_FREQ_PATH, STABILITY_PATH)
    print(f"\nRule B check:")
    print(f"  SP reheat: {rule_b['sp_reheat']}")
    print(f"  MP diversity: {rule_b['mp_diversity']}")
    for reason in rule_b.get("reasons", []):
        print(f"  Skipped: {reason}")

    # Base techniques that get XAI variants
    base_techniques = {
        "SP-CF-AILTA": "SP-SR-LA",  # Primary surrogate from SR data
        "MP-CF": "SP-SR-LA",
    }

    summary = []

    for base_tech in ["SP-CF-AILTA", "MP-CF"]:
        print(f"\n--- Rules for {base_tech} variants ---")

        for domain in DOMAINS:
            print(f"\n  {domain}:")

            # Use SP-SR-LA effectiveness map (unconfounded) for rule derivation
            sr_tech = "SP-SR-LA"

            # Rule A: XAI in-domain
            type_rules = extract_rule_a_for_domain(emap_df, domain, sr_tech)
            h_rules = build_heuristic_level_rules(emap_df, domain, sr_tech, type_rules, TRACES_DIR)

            variant_base = base_tech.replace("-", "_")
            xai_rules = {
                "variant": f"{base_tech}-XAI",
                "base_technique": base_tech,
                "domain": domain,
                "source": "SP-SR-LA effectiveness map",
                "rule_type": "A",
                "type_class_rules": type_rules,
                "heuristic_rules": h_rules,
            }
            if rule_b.get("sp_reheat") and base_tech == "SP-CF-AILTA":
                xai_rules["rule_b"] = {"type": "reheat", "threshold": rule_b["sp_threshold"]}
            if rule_b.get("mp_diversity") and base_tech == "MP-CF":
                xai_rules["rule_b"] = {"type": "diversity", "threshold": rule_b["mp_threshold"]}

            write_rules(xai_rules, RULES_DIR / f"{base_tech}-XAI" / f"{domain}.json")

            # Rule A: LODO
            lodo_rules = build_lodo_rules(emap_df, domain, sr_tech)
            lodo_h_rules = build_heuristic_level_rules(emap_df, domain, sr_tech, lodo_rules, TRACES_DIR)
            lodo_dict = {
                "variant": f"{base_tech}-XAI-LODO",
                "base_technique": base_tech,
                "domain": domain,
                "held_out": domain,
                "source": f"SP-SR-LA effectiveness map (5 domains excl {domain})",
                "rule_type": "A-LODO",
                "type_class_rules": lodo_rules,
                "heuristic_rules": lodo_h_rules,
            }
            write_rules(lodo_dict, RULES_DIR / f"{base_tech}-XAI-LODO" / f"{domain}.json")

            # Control: RAND
            rand_rules = build_random_mask(type_rules, domain)
            rand_h_rules = build_heuristic_level_rules(emap_df, domain, sr_tech, rand_rules, TRACES_DIR)
            rand_dict = {
                "variant": f"{base_tech}-RAND",
                "base_technique": base_tech,
                "domain": domain,
                "source": "random mask (same exclusion count as XAI)",
                "rule_type": "RAND",
                "type_class_rules": rand_rules,
                "heuristic_rules": rand_h_rules,
            }
            write_rules(rand_dict, RULES_DIR / f"{base_tech}-RAND" / f"{domain}.json")

            # Control: STAT
            stat_rules = build_stat_mask(emap_df, domain, sr_tech)
            stat_h_rules = build_heuristic_level_rules(emap_df, domain, sr_tech, stat_rules, TRACES_DIR)
            stat_dict = {
                "variant": f"{base_tech}-STAT",
                "base_technique": base_tech,
                "domain": domain,
                "source": "descriptive statistics only (no surrogate, no SHAP)",
                "rule_type": "STAT",
                "type_class_rules": stat_rules,
                "heuristic_rules": stat_h_rules,
            }
            write_rules(stat_dict, RULES_DIR / f"{base_tech}-STAT" / f"{domain}.json")

            # Print summary
            for phase_name in ["early", "middle", "late"]:
                xai_exc = type_rules.get(phase_name, {}).get("excluded", [])
                lodo_exc = lodo_rules.get(phase_name, {}).get("excluded", [])
                rand_exc = rand_rules.get(phase_name, {}).get("excluded", [])
                stat_exc = stat_rules.get(phase_name, {}).get("excluded", [])
                print(f"    {phase_name:8s}: XAI={xai_exc}, LODO={lodo_exc}, RAND={rand_exc}, STAT={stat_exc}")

                summary.append({
                    "base_technique": base_tech, "domain": domain, "phase": phase_name,
                    "xai_excluded": ",".join(xai_exc) if xai_exc else "none",
                    "lodo_excluded": ",".join(lodo_exc) if lodo_exc else "none",
                    "rand_excluded": ",".join(rand_exc) if rand_exc else "none",
                    "stat_excluded": ",".join(stat_exc) if stat_exc else "none",
                })

    # Write summary
    summary_path = RULES_DIR / "rules_summary.csv"
    pd.DataFrame(summary).to_csv(summary_path, index=False)
    print(f"\nWritten: {summary_path}")
    print("\n=== Phase 2 complete ===")


if __name__ == "__main__":
    main()
