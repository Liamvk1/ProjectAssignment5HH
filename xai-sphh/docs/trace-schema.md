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
| `objective_before` | float64 | Objective value of the incumbent solution before applying the heuristic. |
| `objective_after` | float64 | Objective value of the candidate solution after applying the heuristic. |
| `delta` | float64 | `objective_after - objective_before`. Negative means improvement for minimisation problems. |
| `log_return` | float64 | `log(objective_after / objective_before)`. Undefined when either value is non-positive; written as NaN. |
| `accepted` | bool | Whether the acceptance strategy kept the candidate solution. |
| `best_so_far` | float64 | Best objective value seen at any point during the run up to and including this iteration. |
| `cpu_time_ms` | float64 | Wall-clock time in milliseconds consumed by the heuristic application. |

## Dynamic columns

After the fixed columns, each trace file contains a variable-length block of state feature columns followed by a variable-length block of selection score columns. The feature and score sets are fixed for a given run but may differ between runs with different configurations.

### State features (prefix `feat_`)

Each enabled feature from `config/features.yaml` contributes one column named `feat_<name>`. The list of active feature names is written to the run manifest so that analysis code can recover the feature schema without inspecting the YAML.

### Per-heuristic selection scores (prefix `score_`)

Each heuristic available in the domain contributes one column named `score_<heuristic_id>`. The value is the raw score the selection strategy assigned to that heuristic before selecting. This column group is all-NaN for selection strategies that do not produce a score vector (e.g. SimpleRandom).

## Schema version

Schema version: **1**. Increment the version in this document, in `TraceRecord.java`,
and in `schema.py` whenever a column is added, removed, or renamed.
