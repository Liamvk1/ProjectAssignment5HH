"""
SHAP interaction values for pairwise feature effects.

Extends the global SHAP analysis to capture how pairs of features jointly
influence the surrogate's predictions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt
import seaborn as sns

from xaisphh.figures.style import apply_style


def compute_interaction_values(model: Any, X: pd.DataFrame) -> Any:
    """Compute SHAP interaction values for all feature pairs.

    Interaction values are only tractable for tree-based models via
    ``shap.TreeExplainer``. This function raises a ``TypeError`` if the model
    is not tree-based.

    :param model: fitted tree-based surrogate estimator
    :param X: feature matrix
    :return: 3-D SHAP interaction values array of shape (n_samples, n_features, n_features)
    :raises TypeError: if the model does not support interaction values
    """
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

    base = model
    if hasattr(model, "named_steps"):
        base = list(model.named_steps.values())[-1]

    if not isinstance(base, (GradientBoostingClassifier, RandomForestClassifier)):
        raise TypeError(
            f"SHAP interaction values require a tree-based model "
            f"(GradientBoostingClassifier or RandomForestClassifier), "
            f"got {type(base).__name__}."
        )

    explainer = shap.TreeExplainer(model)
    return explainer.shap_interaction_values(X)


def save_interaction_heatmap(
    interaction_values: Any,
    feature_names: list[str],
    output_path: Path,
) -> None:
    """Save a heatmap of mean absolute interaction values to *output_path*.

    The diagonal entries represent the main effect of each feature on itself;
    off-diagonal entries represent pairwise interaction effects.

    :param interaction_values: 3-D array returned by :func:`compute_interaction_values`
    :param feature_names: ordered list of feature names
    :param output_path: destination path for the saved figure
    """
    apply_style()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Mean absolute interaction value across all samples.
    mean_abs = np.abs(np.array(interaction_values)).mean(axis=0)

    fig, ax = plt.subplots(
        figsize=(max(6, len(feature_names) * 0.5), max(5, len(feature_names) * 0.5))
    )
    sns.heatmap(
        mean_abs,
        xticklabels=feature_names,
        yticklabels=feature_names,
        cmap="Blues",
        ax=ax,
        annot=(len(feature_names) <= 12),
        fmt=".3f",
    )
    ax.set_title("Mean |SHAP interaction value|")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close("all")
