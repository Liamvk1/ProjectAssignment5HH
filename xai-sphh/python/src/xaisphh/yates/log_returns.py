"""
Log-return computation for objective value sequences.

Replicates the log-return measure used in Yates et al. to characterise the
effectiveness of individual heuristics over time.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_log_returns(df: pd.DataFrame) -> pd.Series:
    """Compute the log return for each iteration in the trace.

    The log return at iteration t is defined as
    ``log(objective_after_t / objective_before_t)``.
    Rows where either value is non-positive receive ``NaN``.

    This function replicates the ``log_return`` column already written by the
    Java instrumentation. It is provided here so that the Python pipeline can
    recompute or verify the values independently.

    :param df: trace dataframe containing ``objective_before`` and ``objective_after``
    :return: series of log returns, aligned to *df*'s index
    :raises KeyError: if required columns are absent
    """
    before = df["objective_before"]
    after  = df["objective_after"]

    # Mask rows where either value is non-positive to avoid log(0) or log(negative).
    valid = (before > 0) & (after > 0)

    log_ret = pd.Series(np.nan, index=df.index, dtype="float64")
    log_ret[valid] = np.log(after[valid] / before[valid])
    return log_ret
