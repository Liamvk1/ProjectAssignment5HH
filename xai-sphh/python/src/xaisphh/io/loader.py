"""
Trace file loading and schema validation.

Provides functions to load one or many CSV trace files into a single
:class:`pandas.DataFrame` and validate the result against the schema defined in
:mod:`xaisphh.io.schema`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from xaisphh.io.schema import FIXED_COLUMNS, FIXED_DTYPES


def load_trace(path: Path) -> pd.DataFrame:
    """Load a single CSV trace file and validate its schema.

    Reads the file, checks that all fixed columns are present, casts them to
    the declared dtypes, and returns the dataframe with dynamic columns
    (``feat_*`` and ``score_*``) appended after the fixed ones.

    The ``log_return`` column may contain empty CSV fields (written by
    ``CsvTraceWriter`` for non-positive objectives per DD-08); these are
    loaded as ``NaN`` by pandas automatically.

    :param path: path to the CSV trace file produced by ``CsvTraceWriter``
    :return: validated dataframe with one row per iteration
    :raises FileNotFoundError: if *path* does not exist
    :raises ValueError: if required columns are missing or dtypes cannot be cast
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    df = pd.read_csv(path, dtype=str)  # load everything as str first for safe casting

    # Validate that all fixed columns are present.
    validate_schema(df)

    # Cast fixed columns to their declared dtypes.
    for col, dtype in FIXED_DTYPES.items():
        if dtype == "bool":
            # CSV stores True/False as strings; convert case-insensitively.
            df[col] = df[col].str.strip().str.lower().map(
                {"true": True, "false": False, "1": True, "0": False}
            ).astype("boolean")
        elif dtype in ("float64",):
            # Empty fields (e.g. log_return for non-positive objectives) become NaN.
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        elif dtype == "int64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("int64")
        elif dtype == "int32":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("int32")
        elif dtype == "string":
            df[col] = df[col].astype("string")

    # Cast dynamic feature and score columns to float64.
    dynamic_cols = [c for c in df.columns if c not in FIXED_COLUMNS]
    for col in dynamic_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # Reorder: fixed columns first, then dynamic columns in their original order.
    ordered = FIXED_COLUMNS + [c for c in df.columns if c not in FIXED_COLUMNS]
    return df[ordered]


def load_traces(directory: Path, pattern: str = "*.csv") -> pd.DataFrame:
    """Load all trace files matching *pattern* from *directory* and concatenate them.

    Each file is loaded via :func:`load_trace`. The resulting dataframes are
    concatenated along the row axis with the index reset.

    :param directory: directory containing CSV trace files
    :param pattern: glob pattern used to find trace files within *directory*
    :return: concatenated dataframe of all traces
    :raises FileNotFoundError: if *directory* does not exist
    :raises ValueError: if no matching files are found
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Trace directory not found: {directory}")

    files = sorted(directory.glob(pattern))
    if not files:
        raise ValueError(
            f"No files matching '{pattern}' found in {directory}."
        )

    frames = [load_trace(f) for f in files]
    return pd.concat(frames, ignore_index=True)


def validate_schema(df: pd.DataFrame) -> None:
    """Assert that *df* contains all required fixed columns.

    :param df: dataframe to validate
    :raises ValueError: if any fixed column is absent
    """
    missing = [col for col in FIXED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Trace dataframe is missing required fixed columns: {missing}. "
            f"Present columns: {list(df.columns)}"
        )
