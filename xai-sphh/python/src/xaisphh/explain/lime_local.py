"""
LIME local explanations for individual hyper-heuristic decisions.

Provides local explanations for specific iterations of interest, such as the
first decision after a long period without improvement or the decision that led
to the best-found solution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from lime.lime_tabular import LimeTabularExplainer

from xaisphh.figures.style import apply_style


def explain_instance(
    model: Any,
    X: pd.DataFrame,
    instance_index: int,
    num_features: int = 10,
    num_samples: int = 5000,
) -> Any:
    """Compute a LIME explanation for the decision at *instance_index*.

    :param model: fitted surrogate estimator
    :param X: feature matrix from which the instance is taken
    :param instance_index: row index of the decision to explain
    :param num_features: maximum number of features to include in the explanation
    :param num_samples: number of perturbed samples used by LIME
    :return: ``lime.explanation.Explanation`` object
    """
    feature_names = list(X.columns)
    X_array = X.to_numpy()

    explainer = LimeTabularExplainer(
        training_data=X_array,
        feature_names=feature_names,
        class_names=["rejected", "accepted"],
        mode="classification",
        discretize_continuous=True,
        random_state=42,
    )

    instance = X_array[instance_index]

    explanation = explainer.explain_instance(
        data_row=instance,
        predict_fn=model.predict_proba,
        num_features=num_features,
        num_samples=num_samples,
    )

    return explanation


def save_explanation_plot(explanation: Any, output_path: Path) -> None:
    """Save the LIME explanation as a figure to *output_path*.

    :param explanation: ``lime.explanation.Explanation`` object
    :param output_path: destination path for the saved figure
    """
    apply_style()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig = explanation.as_pyplot_figure()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close("all")
