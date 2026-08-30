"""
Feature matrix assembly for surrogate model training.

Transforms a raw trace dataframe into the (X, y) pair expected by
:mod:`xaisphh.surrogate.train`. The target variable is whether the
hyper-heuristic accepted the candidate solution (the ``accepted`` column).
"""

from __future__ import annotations

import pandas as pd


def build_feature_matrix(
    df: pd.DataFrame,
    drop_score_columns: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Assemble the model-ready feature matrix and binary target.

    Selects all ``feat_*`` columns as predictors. Optionally includes ``score_*``
    columns. The target is the ``accepted`` column cast to integer (1 accepted,
    0 rejected).

    :param df: validated trace dataframe loaded by :mod:`xaisphh.io.loader`
    :param drop_score_columns: if ``True``, exclude ``score_*`` columns from X
    :return: tuple of (X, y) where X is the feature matrix and y is the target series
    :raises ValueError: if no ``feat_*`` columns are found in *df*
    """
    raise NotImplementedError(
        "TODO: select feat_* columns (and optionally score_* columns) from df, "
        "return (X, df['accepted'].astype(int)) as (DataFrame, Series)."
    )
