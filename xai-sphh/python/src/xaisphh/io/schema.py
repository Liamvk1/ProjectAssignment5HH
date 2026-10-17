"""
Trace file schema definition.

This module is the Python mirror of ``TraceRecord.FIXED_COLUMNS`` in the Java source
and of the column table in ``docs/trace-schema.md``. All three must agree.

The column list and dtype map defined here are used by :mod:`xaisphh.io.loader` to
validate loaded dataframes and by the test suite to assert cross-language consistency.

Schema version: 2
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Fixed columns
# ---------------------------------------------------------------------------

#: Ordered list of fixed column names, matching ``docs/trace-schema.md`` exactly.
#: Do not reorder or rename without bumping SCHEMA_VERSION and updating the doc.
FIXED_COLUMNS: list[str] = [
    "run_id",
    "iteration",
    "heuristic_id",
    "heuristic_class",
    "depth_of_search",
    "intensity_of_mutation",
    "target_index",
    "source_index",
    "second_parent_index",
    "objective_before",
    "objective_after",
    "delta",
    "log_return",
    "accepted",
    "best_so_far",
    "cpu_time_ms",
    "pop_best",
    "pop_mean",
    "pop_diversity",
]

#: Schema version. Increment when any column is added, removed, or renamed.
SCHEMA_VERSION: int = 2

# ---------------------------------------------------------------------------
# Column dtype hints (used for efficient Parquet storage and validation)
# ---------------------------------------------------------------------------

#: Mapping from fixed column name to the pandas dtype to use after loading.
FIXED_DTYPES: dict[str, str] = {
    "run_id":                "string",
    "iteration":             "int64",
    "heuristic_id":          "int32",
    "heuristic_class":       "string",
    "depth_of_search":       "float64",
    "intensity_of_mutation": "float64",
    "target_index":          "int32",
    "source_index":          "int32",
    "second_parent_index":   "int32",
    "objective_before":      "float64",
    "objective_after":       "float64",
    "delta":                 "float64",
    "log_return":            "float64",
    "accepted":              "bool",
    "best_so_far":           "float64",
    "cpu_time_ms":           "float64",
    "pop_best":              "float64",
    "pop_mean":              "float64",
    "pop_diversity":         "float64",
}

# ---------------------------------------------------------------------------
# Dynamic column prefixes
# ---------------------------------------------------------------------------

#: Prefix for state feature columns. Example: ``feat_budget_progress``.
FEAT_PREFIX: str = "feat_"

#: Prefix for per-heuristic selection score columns. Example: ``score_3``.
SCORE_PREFIX: str = "score_"


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the names of all feature columns present in *df*.

    Feature columns are those whose names begin with :data:`FEAT_PREFIX`.

    :param df: a dataframe loaded from a trace file
    :return: list of feature column names in their original order
    """
    return [c for c in df.columns if c.startswith(FEAT_PREFIX)]


def score_columns(df: pd.DataFrame) -> list[str]:
    """Return the names of all score columns present in *df*.

    Score columns are those whose names begin with :data:`SCORE_PREFIX`.

    :param df: a dataframe loaded from a trace file
    :return: list of score column names in their original order
    """
    return [c for c in df.columns if c.startswith(SCORE_PREFIX)]
