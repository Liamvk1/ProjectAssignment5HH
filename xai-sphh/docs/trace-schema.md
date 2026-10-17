# Trace Schema

This document is the single source of truth for the trace file column specification.
Both `TraceRecord.java` and `python/src/xaisphh/io/schema.py` mirror this list.
Tests on both sides assert that their column lists match this document exactly.

## Fixed columns

The following columns appear in every trace file, in this order.

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | string | Unique identifier for the run (UUID). |
| `iteration` | int64 | Zero-based iteration counter within the run. |
| `heuristic_id` | int32 | Index of the low-level heuristic that was selected. |
| `heuristic_class` | string | HyFlex heuristic type: `MUTATION`, `RUIN_RECREATE`, `LOCAL_SEARCH`, or `CROSSOVER`. |
| `depth_of_search` | float64 | Depth-of-search parameter passed to HyFlex at this step (0.0 to 1.0). |
| `intensity_of_mutation` | float64 | Intensity-of-mutation parameter passed to HyFlex at this step (0.0 to 1.0). |
| `target_index` | int32 | Solution memory slot of the individual targeted at this step. For single-point search this is always the incumbent slot (0). |
| `source_index` | int32 | Solution memory slot used as the primary source for the heuristic. For unary heuristics this equals `target_index`. |
| `second_parent_index` | int32 | Slot of the second parent for crossover heuristics, or -1 when the heuristic is not a crossover. |
| `objective_before` | float64 | Objective value of the target individual before applying the heuristic. |
| `objective_after` | float64 | Objective value of the candidate solution after applying the heuristic. |
| `delta` | float64 | `objective_after - objective_before`. Negative means improvement for minimisation problems. |
| `log_return` | float64 | `log(objective_after / objective_before)`. Written as an empty field (not NaN or infinity) when either value is non-positive, to preserve Pandas float dtype on load (design decision DD-08). |
| `accepted` | bool | Whether the candidate was accepted: kept by the acceptance strategy for single-point search, or replaced the target for multi-point search. |
| `best_so_far` | float64 | Best objective value seen at any point during the run up to and including this iteration. |
| `cpu_time_ms` | float64 | Wall-clock time in milliseconds consumed by the heuristic application only, excluding logging and feature extraction overhead. |
| `pop_best` | float64 | Best objective in the population at this step. For single-point search equals `best_so_far`. |
| `pop_mean` | float64 | Mean objective across the population. For single-point search equals `objective_before`. |
| `pop_diversity` | float64 | Coefficient of variation (standard deviation / mean) of population objectives. Zero for single-point search; NaN when mean is zero. |

## Dynamic columns

After the fixed columns, each trace file contains a variable-length block of state feature columns followed by a variable-length block of selection score columns. The feature and score sets are fixed for a given run but may differ between runs with different configurations.

### State features (prefix `feat_`)

Each enabled feature from `config/features.yaml` contributes one column named `feat_<name>`. The list of active feature names is written to the run manifest so that analysis code can recover the feature schema without inspecting the YAML.

The current default feature set (Decision 28) is:

| Feature | Type | Description |
|---------|------|-------------|
| `feat_llh_count` | int | Number of low-level heuristics available in the domain. |
| `feat_progress` | float64 | Fraction of the total budget consumed at decision time. |
| `feat_obj_norm` | float64 | Current objective normalised by the running observed range (running min/max only; never the full-run range). |
| `feat_gap_to_best` | float64 | `(current - best_so_far) / running_range`. |
| `feat_iters_since_improve` | int | Applications since best-so-far last improved. |
| `feat_improve_rate_50` | float64 | Fraction of the last 50 applications where `objective_after < objective_before`. |
| `feat_mean_logret_50` | float64 | Mean log return over the last 50 applications (NaN entries excluded). |
| `feat_last_h1` | int | Index of the most recently applied heuristic (-1 if none). Categorical, not ordinal. |
| `feat_last_h2` | int | Index of the second most recently applied heuristic (-1 if none). Categorical. |
| `feat_last_h3` | int | Index of the third most recently applied heuristic (-1 if none). Categorical. |
| `feat_last_class1` | int | HeuristicType ordinal of the most recently applied heuristic (-1 if none). MUTATION=0, RUIN_RECREATE=1, LOCAL_SEARCH=2, CROSSOVER=3. Categorical. |
| `feat_last_class2` | int | HeuristicType ordinal of the second most recent heuristic (-1 if none). Categorical. |
| `feat_last_class3` | int | HeuristicType ordinal of the third most recent heuristic (-1 if none). Categorical. |
| `feat_iters_since_accept` | int | Applications since the last accepted move. |
| `feat_pop_diversity` | float64 | Population diversity (coefficient of variation of objectives). NaN for single-point search. |
| `feat_pop_target_rank` | int | Rank of the target individual within the population (0 = best). -1 for single-point search. |

### Per-heuristic selection scores (prefix `score_`)

Each heuristic available in the domain contributes one column named `score_<heuristic_id>`. The value is the raw score the selection strategy assigned to that heuristic before selecting. This column group is all-empty for selection strategies that do not produce a score vector (e.g. SimpleRandom).

## Schema version

Schema version: **2**. Increment the version in this document, in `TraceRecord.java`,
and in `schema.py` whenever a column is added, removed, or renamed.

### Version history

| Version | Change |
|---------|--------|
| 1 | Initial schema with 13 fixed columns. |
| 2 | Added `target_index`, `source_index`, `second_parent_index`, `pop_best`, `pop_mean`, `pop_diversity` (Decision 27). Changed `log_return` non-positive handling from NaN literal to empty field (DD-08). Updated feature set to Decision 28 specification. |
