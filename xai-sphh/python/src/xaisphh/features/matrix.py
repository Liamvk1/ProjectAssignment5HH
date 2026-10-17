"""
Feature matrix assembly for surrogate model training.

Transforms a raw trace dataframe into the (X, y) pair expected by
:mod:`xaisphh.surrogate.train`. The target variable is whether the
hyper-heuristic accepted the candidate solution (the ``accepted`` column).
"""

from __future__ import annotations

import pandas as pd

from xaisphh.io.schema import FEAT_PREFIX, SCORE_PREFIX


def build_feature_matrix(
    df: pd.DataFrame,
    drop_score_columns: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Assemble the model-ready feature matrix and binary target.

    Selects all ``feat_*`` columns as predictors. Optionally includes ``score_*``
    columns. The target is the ``accepted`` column cast to integer (1 accepted,
    0 rejected).

    Rows where any feature column is NaN are dropped before returning, since
    scikit-learn estimators do not accept NaN values by default.

    :param df: validated trace dataframe loaded by :mod:`xaisphh.io.loader`
    :param drop_score_columns: if ``True``, exclude ``score_*`` columns from X
    :return: tuple of (X, y) where X is the feature matrix and y is the target series
    :raises ValueError: if no ``feat_*`` columns are found in *df*
    """
    feat_cols = [c for c in df.columns if c.startswith(FEAT_PREFIX)]
    if not feat_cols:
        raise ValueError(
            f"No feature columns (prefix '{FEAT_PREFIX}') found in the dataframe. "
            f"Available columns: {list(df.columns)}"
        )

    score_cols: list[str] = []
    if not drop_score_columns:
        score_cols = [c for c in df.columns if c.startswith(SCORE_PREFIX)]

    X_cols = feat_cols + score_cols
    X = df[X_cols].copy()
    y = df["accepted"].astype(int)

    # Fill NaN with -1.0 (the project-wide sentinel for "not applicable").
    # Population features are NaN for single-point search; score columns are NaN
    # for non-scoring selectors (e.g. SimpleRandom). Using -1.0 is consistent with
    # the Java FeatureExtractor sentinel for missing categorical values and allows
    # the surrogate to distinguish "absent" from any real feature value.
    X = X.fillna(-1.0)

    return X, y
