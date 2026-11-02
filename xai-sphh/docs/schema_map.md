# Trace Schema Map

Column-by-column mapping for every field in the Assessment 5 trace files.
Schema version 2; 19 fixed columns + 16 feat_ columns + variable score_ columns.

## Fixed Columns (19)

| # | Column | Type | Meaning |
|---|--------|------|---------|
| 1 | `run_id` | string | UUID identifying this run uniquely |
| 2 | `iteration` | int64 | Zero-based heuristic application counter |
| 3 | `heuristic_id` | int32 | Index of the low-level heuristic applied in this row |
| 4 | `heuristic_class` | string | HyFlex type of the applied heuristic: MUTATION, RUIN_RECREATE, LOCAL_SEARCH, or CROSSOVER |
| 5 | `depth_of_search` | float64 | HyFlex depth-of-search parameter (fixed 0.1 in all techniques) |
| 6 | `intensity_of_mutation` | float64 | HyFlex intensity-of-mutation parameter (fixed 0.1 in all techniques) |
| 7 | `target_index` | int32 | Solution memory slot targeted. SP: always 0 (incumbent). MP: binary-tournament worst individual |
| 8 | `source_index` | int32 | Primary source slot. SP: always 0. MP: same as target_index for unary heuristics |
| 9 | `second_parent_index` | int32 | Second parent slot for crossover, or -1 for non-crossover heuristics |
| 10 | `objective_before` | float64 | Objective of the target individual before heuristic application |
| 11 | `objective_after` | float64 | Objective of the candidate solution after heuristic application |
| 12 | `delta` | float64 | objective_after - objective_before. Negative = improvement (minimisation) |
| 13 | `log_return` | float64 | log(objective_after / objective_before). Empty field when either value is non-positive (DD-08) |
| 14 | `accepted` | bool | Whether the candidate was accepted (SP: by acceptance strategy; MP: by replacement rule) |
| 15 | `best_so_far` | float64 | Best objective seen in the entire run up to and including this row |
| 16 | `cpu_time_ms` | float64 | Wall-clock milliseconds for the heuristic application only |
| 17 | `pop_best` | float64 | Best objective in the population. SP: equals best_so_far |
| 18 | `pop_mean` | float64 | Mean objective across the population. SP: equals objective_before |
| 19 | `pop_diversity` | float64 | Coefficient of variation of population objectives. SP: 0.0; NaN when mean is 0 |

## State Feature Columns (16, prefix `feat_`)

All features are computed before the heuristic is applied (no leakage from the outcome).

| Column | Type | Category | Meaning |
|--------|------|----------|---------|
| `feat_llh_count` | int | Structural | Number of LLHs in this domain. Constant per domain; EXCLUDED from all surrogates |
| `feat_progress` | float64 | Search progress | Budget fraction consumed: iteration / total_budget |
| `feat_obj_norm` | float64 | Solution quality | Incumbent objective normalised by running observed range |
| `feat_gap_to_best` | float64 | Solution quality | (incumbent - best_so_far) / running_range |
| `feat_iters_since_improve` | int | Stagnation | Applications since best_so_far last improved |
| `feat_improve_rate_50` | float64 | Recent performance | Fraction of last 50 applications with delta < 0 |
| `feat_mean_logret_50` | float64 | Recent performance | Mean log return over last 50 applications (NaN excluded) |
| `feat_last_h1` | int | Heuristic history | Index of most recently applied heuristic (-1 if none). Categorical |
| `feat_last_h2` | int | Heuristic history | Index of 2nd most recently applied heuristic. Categorical |
| `feat_last_h3` | int | Heuristic history | Index of 3rd most recently applied heuristic. Categorical |
| `feat_last_class1` | int | Heuristic history | HyFlex type ordinal of most recent heuristic (MUTATION=0, RUIN_RECREATE=1, LOCAL_SEARCH=2, CROSSOVER=3). Categorical |
| `feat_last_class2` | int | Heuristic history | Type ordinal of 2nd most recent heuristic. Categorical |
| `feat_last_class3` | int | Heuristic history | Type ordinal of 3rd most recent heuristic. Categorical |
| `feat_iters_since_accept` | int | Stagnation | Applications since last accepted move |
| `feat_pop_diversity` | float64 | Population (MP only) | Population CoV. NaN for single-point search |
| `feat_pop_target_rank` | int | Population (MP only) | Rank of target individual in population (0=best). -1 for SP |

## Selection Score Columns (prefix `score_`)

| Column | Type | Meaning |
|--------|------|---------|
| `score_0` .. `score_N` | float64 | Raw Choice Function score for heuristic i before selection. NaN during CF warm-up. All-empty for SimpleRandom |

The number of score columns equals the domain's heuristic count (SAT=11, BinPacking=8, FlowShop=15, TSP=13, VRP=10, PersonnelScheduling=12).

## Key Columns for Phase 1 (Effectiveness Surrogates)

| Role | Column(s) |
|------|-----------|
| Current heuristic (the one being evaluated) | `heuristic_id`, `heuristic_class` |
| Improvement label | Derived: `improved = 1 if objective_after < objective_before` |
| Wasted application label | Derived: `delta_null = 1 if objective_after == objective_before` |
| Pre-application state features | All `feat_*` except `feat_llh_count` |
| Objective before (for MP target) | `objective_before` |
| Objective after | `objective_after` (excluded from features, used only for labels) |
| Acceptance outcome | `accepted` (excluded from effectiveness features) |
| Progress band | Derived from `feat_progress`: band = floor(feat_progress * 10), capped at 9 |
