"""
Spearman footrule distance between heuristic rankings.

Replicates the footrule-based comparison measure used in Yates et al. to
quantify how much the ranking of heuristics changes between phases of the search
or between different runs.
"""

from __future__ import annotations

import pandas as pd


def heuristic_ranking(
    df: pd.DataFrame,
    score_column: str = "objective_after",
    groupby: str = "heuristic_id",
) -> pd.Series:
    """Rank heuristics by their mean effect on the objective value.

    For minimisation problems a lower mean objective is better, so the heuristic
    with the lowest mean receives rank 1.

    :param df: trace dataframe
    :param score_column: column whose mean is used to rank heuristics
    :param groupby: column containing heuristic identifiers
    :return: series mapping heuristic id to rank (1 = best, i.e. lowest mean)
    """
    means = df.groupby(groupby)[score_column].mean()
    # ascending=True: lowest mean (best for minimisation) gets rank 1.
    return means.rank(ascending=True, method="average")


def footrule_distance(ranking_a: pd.Series, ranking_b: pd.Series) -> float:
    """Compute the Spearman footrule distance between two heuristic rankings.

    The footrule distance is the sum of absolute rank differences over all
    heuristics present in both rankings.

    :param ranking_a: series mapping heuristic id to rank
    :param ranking_b: series mapping heuristic id to rank
    :return: non-negative footrule distance; 0 means identical rankings
    :raises ValueError: if the two rankings do not contain the same heuristic ids
    """
    if set(ranking_a.index) != set(ranking_b.index):
        only_a = set(ranking_a.index) - set(ranking_b.index)
        only_b = set(ranking_b.index) - set(ranking_a.index)
        raise ValueError(
            f"Rankings have different heuristic ids. "
            f"Only in A: {only_a}. Only in B: {only_b}."
        )

    # Align on shared index before differencing.
    a, b = ranking_a.align(ranking_b, join="inner")
    return float((a - b).abs().sum())
