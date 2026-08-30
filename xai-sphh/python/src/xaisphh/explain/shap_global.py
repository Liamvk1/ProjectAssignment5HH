"""
Global SHAP explanation of the surrogate model.

Computes SHAP values for all predictions and aggregates them into global
feature importance and summary plots.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def compute_shap_values(model: Any, X: pd.DataFrame) -> Any:
    """Compute SHAP values for every row in *X* using the appropriate explainer.

    Selects a TreeExplainer for tree-based models and a KernelExplainer otherwise.

    :param model: fitted surrogate estimator
    :param X: feature matrix for which SHAP values are computed
    :return: SHAP values object (``shap.Explanation`` or ndarray)
    """
    # TODO (DD-06): Implement SHAP value computation. Choose TreeExplainer vs
    #               KernelExplainer based on model type. Consider whether to use
    #               a background dataset for KernelExplainer summarisation.
    raise NotImplementedError(
        "TODO (DD-06): implement SHAP value computation. "
        "See design-decisions.md DD-06."
    )


def global_feature_importance(
    shap_values: Any,
    feature_names: list[str],
) -> pd.DataFrame:
    """Aggregate SHAP values into a global feature importance table.

    :param shap_values: SHAP values returned by :func:`compute_shap_values`
    :param feature_names: ordered list of feature names matching the matrix columns
    :return: dataframe with columns ``feature`` and ``mean_abs_shap``,
             sorted descending by ``mean_abs_shap``
    """
    raise NotImplementedError(
        "TODO (DD-06): aggregate SHAP values to global importance."
    )


def save_summary_plot(
    shap_values: Any,
    X: pd.DataFrame,
    output_path: Path,
) -> None:
    """Save a SHAP summary (beeswarm) plot to *output_path*.

    :param shap_values: SHAP values returned by :func:`compute_shap_values`
    :param X: feature matrix, used for feature value colouring
    :param output_path: destination path for the saved figure (PDF or PNG)
    """
    raise NotImplementedError(
        "TODO (DD-06): implement SHAP summary plot generation."
    )
