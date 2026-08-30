"""
LIME local explanations for individual hyper-heuristic decisions.

Provides local explanations for specific iterations of interest, such as the
first decision after a long period without improvement or the decision that led
to the best-found solution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


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
    # TODO (DD-06): Implement local LIME explanation. Instantiate a
    #               LimeTabularExplainer, call explain_instance, and return the result.
    raise NotImplementedError(
        "TODO (DD-06): implement LIME local explanation. "
        "See design-decisions.md DD-06."
    )


def save_explanation_plot(explanation: Any, output_path: Path) -> None:
    """Save the LIME explanation as a figure to *output_path*.

    :param explanation: ``lime.explanation.Explanation`` object
    :param output_path: destination path for the saved figure
    """
    raise NotImplementedError(
        "TODO (DD-06): implement LIME explanation figure export."
    )
