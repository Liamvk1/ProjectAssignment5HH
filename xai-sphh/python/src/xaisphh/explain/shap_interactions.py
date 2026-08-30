"""
SHAP interaction values for pairwise feature effects.

Extends the global SHAP analysis to capture how pairs of features jointly
influence the surrogate's predictions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def compute_interaction_values(model: Any, X: pd.DataFrame) -> Any:
    """Compute SHAP interaction values for all feature pairs.

    Interaction values are only tractable for tree-based models via
    ``shap.TreeExplainer`` with ``interactions=True``. This function will raise
    a ``TypeError`` if the model is not tree-based.

    :param model: fitted tree-based surrogate estimator
    :param X: feature matrix
    :return: 3-D SHAP interaction values array of shape (n_samples, n_features, n_features)
    :raises TypeError: if the model does not support interaction values
    """
    # TODO (DD-06): Implement interaction value computation using
    #               shap.TreeExplainer(model).shap_interaction_values(X).
    raise NotImplementedError(
        "TODO (DD-06): implement SHAP interaction value computation."
    )


def save_interaction_heatmap(
    interaction_values: Any,
    feature_names: list[str],
    output_path: Path,
) -> None:
    """Save a heatmap of mean absolute interaction values to *output_path*.

    :param interaction_values: array returned by :func:`compute_interaction_values`
    :param feature_names: ordered list of feature names
    :param output_path: destination path for the saved figure
    """
    raise NotImplementedError(
        "TODO (DD-06): implement interaction heatmap generation."
    )
