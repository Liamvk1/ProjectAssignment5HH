"""
Log-return computation for objective value sequences.

Replicates the log-return measure used in Yates et al. to characterise the
effectiveness of individual heuristics over time.
"""

from __future__ import annotations

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
    raise NotImplementedError(
        "TODO: implement log return computation. "
        "Use np.log(df['objective_after'] / df['objective_before']), "
        "replacing non-positive values with NaN."
    )
