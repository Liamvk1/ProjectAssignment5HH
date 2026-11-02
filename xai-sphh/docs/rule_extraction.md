# Rule Extraction Procedure

This document describes the fully deterministic procedure used to derive selection masks from the Phase 1 effectiveness surrogates. Every threshold is either stated in this document or computed from the data; no hand-tuning is involved.

## Source Data

The rules are derived from the **effectiveness map** (`results/rq1/effectiveness_map/effectiveness_map.csv`), which contains for every domain x heuristic type class x progress band:

- `observed_improvement_rate`: fraction of heuristic applications that produced `objective_after < objective_before`
- `mean_shap_contribution`: signed mean SHAP value for the heuristic-type one-hot feature (`h_is_MUTATION`, etc.) — positive means the surrogate associates this type with improvement
- `n_seeds_negative`: number of seeds (out of 10) where the signed SHAP contribution was negative
- `n_applications`: total applications in this cell

The primary surrogates are trained on **SP-SR-LA** traces (Simple Random selection), which provide an unconfounded sample of heuristic effectiveness across states — under random selection, the heuristic applied is independent of the search state.

## Phase Definitions

The 10 progress bands (0-9) are merged into 3 phases:

| Phase | Bands | Progress range |
|-------|-------|---------------|
| Early | 0, 1, 2 | 0.0 - 0.3 |
| Middle | 3, 4, 5, 6 | 0.3 - 0.7 |
| Late | 7, 8, 9 | 0.7 - 1.0 |

## Rule A: Selection Mask

For each domain and phase, a heuristic type class is **excluded** if ALL THREE conditions hold:

### Condition (a): SHAP direction
The signed SHAP contribution for `h_is_<TYPE>` is negative in at least **8 out of 10** seeds. This means the surrogate consistently associates this type with non-improvement across independent runs.

### Condition (b): Observed improvement rate
The type's observed improvement rate is below **half the domain-phase mean**. This confirms the SHAP signal with a model-free check — the type genuinely improves less often than average.

### Condition (c): At least one type remains
At least one heuristic type class must remain allowed in every phase. If all types would be excluded, the type with the highest observed improvement rate is retained.

## Variants

### XAI (in-domain)
Rules derived from the domain's own SP-SR-LA effectiveness map. Both type-class-level and heuristic-index-level rules are emitted (the latter maps type exclusions to specific HyFlex heuristic indices using the domain's type-to-index mapping).

### XAI-LODO (leave-one-domain-out)
For each held-out domain, rules are derived from the other 5 domains using **majority vote**: a type class is excluded in a phase if more than half of the other domains exclude it (per the same conditions a, b, c). Rules are at the type-class level only.

### RAND (random control)
A random mask that excludes the **same number** of type-class x phase cells as the XAI mask for that domain, chosen uniformly at random with seed 12345. Tests whether any restriction helps, vs. the specific XAI-chosen restriction.

### STAT (statistics control)
A mask built using only **observed improvement rates** (condition b only, no SHAP/surrogate). A type is excluded if its improvement rate is below half the domain-phase mean. Tests whether the XAI surrogate adds information beyond simple descriptive statistics.

## Rule B: Optional Triggers

### SP-CF-AILTA reheat trigger
If the LIME condition involving `feat_iters_since_improve` has Kendall's tau >= 0.5 across seeds, a threshold reheat is added: when `feat_iters_since_improve` exceeds the threshold from the dominant LIME stagnation condition, the AILTA acceptance threshold is temporarily reset.

### MP-CF diversity trigger
If the LIME condition involving `feat_pop_diversity` has Kendall's tau >= 0.5 across seeds, a diversity trigger is added: when population diversity falls below the LIME-derived threshold, only heuristic types marked as effective in low-diversity states are allowed.

Rule B is only implemented if the relevant condition passes the fidelity gate. Otherwise it is logged as skipped with the reason.

## Output Format

Each rules file is JSON with structure:
```json
{
  "variant": "SP-CF-AILTA-XAI",
  "base_technique": "SP-CF-AILTA",
  "domain": "SAT",
  "source": "SP-SR-LA effectiveness map",
  "rule_type": "A",
  "type_class_rules": {
    "early": {
      "excluded": ["CROSSOVER"],
      "allowed": ["LOCAL_SEARCH", "MUTATION", "RUIN_RECREATE"]
    },
    "middle": { ... },
    "late": { ... }
  },
  "heuristic_rules": {
    "early": {
      "excluded_heuristics": [8, 9, 10],
      "allowed_heuristics": [0, 1, 2, 3, 4, 5, 6, 7]
    },
    ...
  }
}
```

## Determinism

Given the same trace data and seeds, this procedure produces identical rules. The only sources of randomness are:
- The RAND control mask (seeded with 12345)
- The surrogate training (seeded per run seed)
- SHAP and LIME sampling (seeded with 42)
