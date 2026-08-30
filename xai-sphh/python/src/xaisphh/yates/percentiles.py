"""
Percentile bucketing of objective values.

Replicates the percentile-based normalisation used in Yates et al. to place
objective values on a common scale across domains with different objective ranges.
"""

from __future__ import annotations

import pandas as pd


def percentile_rank(series: pd.Series) -> pd.Series:
    """Map each value in *series* to its percentile rank within the series.

    Values are ranked from 0.0 (smallest) to 1.0 (largest). Ties receive the
    average rank.

    :param series: numeric series to rank
    :return: series of percentile ranks in [0.0, 1.0], same index as *series*
    """
    raise NotImplementedError(
        "TODO: implement percentile ranking using series.rank(pct=True)."
    )


def bucket_objectives(
    df: pd.DataFrame,
    column: str = "objective_after",
    n_buckets: int = 10,
) -> pd.Series:
    """Assign each objective value in *column* to one of *n_buckets* equal-width buckets.

    :param df: trace dataframe
    :param column: name of the column to bucket
    :param n_buckets: number of equal-width percentile buckets
    :return: integer series of bucket indices (0 to n_buckets - 1)
    """
    raise NotImplementedError(
        "TODO: implement percentile bucketing using pd.qcut."
    )
