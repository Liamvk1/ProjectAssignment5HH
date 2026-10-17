"""
Global SHAP explanation of the surrogate model.

Computes SHAP values for all predictions and aggregates them into global
feature importance and summary plots.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt

from xaisphh.figures.style import apply_style


def compute_shap_values(model: Any, X: pd.DataFrame) -> Any:
    """Compute SHAP values for every row in *X* using the appropriate explainer.

    Selects a TreeExplainer for tree-based models (GradientBoostingClassifier,
    RandomForestClassifier) and a KernelExplainer for all others (e.g. logistic
    regression wrapped in a Pipeline). The background dataset for KernelExplainer
    is summarised to at most 100 representative rows via k-means to keep
    computation tractable.

    :param model: fitted surrogate estimator
    :param X: feature matrix for which SHAP values are computed
    :return: SHAP values as a 2-D numpy array of shape (n_samples, n_features)
    """
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

    # Unwrap Pipeline to check the underlying estimator.
    base = model
    if hasattr(model, "named_steps"):
        # Pipeline: the last step is the classifier.
        base = list(model.named_steps.values())[-1]

    if isinstance(base, (GradientBoostingClassifier, RandomForestClassifier)):
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        # GradientBoosting returns a single array; RandomForest may return a list.
        if isinstance(shap_values, list):
            # Binary classification: index 1 = positive class (accepted).
            shap_values = shap_values[1]
    else:
        # KernelExplainer: summarise background to reduce computation.
        background = shap.kmeans(X, min(100, len(X)))
        explainer = shap.KernelExplainer(model.predict_proba, background)
        shap_values = explainer.shap_values(X, nsamples=200)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]

    return shap_values


def global_feature_importance(
    shap_values: Any,
    feature_names: list[str],
) -> pd.DataFrame:
    """Aggregate SHAP values into a global feature importance table.

    :param shap_values: SHAP values as a 2-D array of shape (n_samples, n_features)
    :param feature_names: ordered list of feature names matching the matrix columns
    :return: dataframe with columns ``feature`` and ``mean_abs_shap``,
             sorted descending by ``mean_abs_shap``
    """
    mean_abs = np.abs(np.array(shap_values)).mean(axis=0)
    importance = pd.DataFrame({
        "feature":       feature_names,
        "mean_abs_shap": mean_abs,
    })
    return importance.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)


def save_summary_plot(
    shap_values: Any,
    X: pd.DataFrame,
    output_path: Path,
) -> None:
    """Save a SHAP summary (beeswarm) plot to *output_path*.

    :param shap_values: SHAP values as returned by :func:`compute_shap_values`
    :param X: feature matrix, used for feature value colouring
    :param output_path: destination path for the saved figure (PDF or PNG)
    """
    apply_style()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots()
    shap.summary_plot(shap_values, X, show=False)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close("all")
