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

    :param path: path to the CSV trace file produced by ``CsvTraceWriter``
    :return: validated dataframe with one row per iteration
    :raises FileNotFoundError: if *path* does not exist
    :raises ValueError: if required columns are missing or dtypes cannot be cast
    """
    raise NotImplementedError(
        "TODO: implement trace loading. "
        "Use pd.read_csv, validate fixed columns against FIXED_COLUMNS, "
        "cast dtypes using FIXED_DTYPES, and return the dataframe."
    )


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
    raise NotImplementedError(
        "TODO: implement multi-trace loading. "
        "Glob the directory, call load_trace on each file, and pd.concat the results."
    )


def validate_schema(df: pd.DataFrame) -> None:
    """Assert that *df* contains all required fixed columns.

    :param df: dataframe to validate
    :raises ValueError: if any fixed column is absent
    """
    raise NotImplementedError(
        "TODO: implement schema validation. "
        "Check that all names in FIXED_COLUMNS are present in df.columns."
    )
