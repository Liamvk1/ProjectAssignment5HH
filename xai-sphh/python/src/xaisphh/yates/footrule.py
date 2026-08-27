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

    :param df: trace dataframe
    :param score_column: column whose mean is used to rank heuristics
    :param groupby: column containing heuristic identifiers
    :return: series mapping heuristic id to rank (1 = best)
    """
    raise NotImplementedError(
        "TODO: group by heuristic_id, compute mean of score_column, "
        "then rank ascending (lower objective is better for minimisation)."
    )


def footrule_distance(ranking_a: pd.Series, ranking_b: pd.Series) -> float:
    """Compute the Spearman footrule distance between two heuristic rankings.

    The footrule distance is the sum of absolute rank differences over all
    heuristics present in both rankings.

    :param ranking_a: series mapping heuristic id to rank
    :param ranking_b: series mapping heuristic id to rank
    :return: non-negative footrule distance; 0 means identical rankings
    :raises ValueError: if the two rankings do not contain the same heuristic ids
    """
    raise NotImplementedError(
        "TODO: align the two series on their index, compute |rank_a - rank_b|, "
        "sum, and return as float."
    )
