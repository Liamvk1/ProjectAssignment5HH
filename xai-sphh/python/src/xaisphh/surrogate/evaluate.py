"""
Surrogate model faithfulness evaluation.

A surrogate model that does not accurately approximate the hyper-heuristic's
decisions explains nothing meaningful. This module computes faithfulness metrics
to quantify how well the surrogate matches the observed decisions before any
SHAP or LIME analysis is performed.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def faithfulness_score(
    model: Any,
    X: pd.DataFrame,
    y: pd.Series,
) -> dict[str, float]:
    """Compute faithfulness metrics for the surrogate model.

    Returns a dictionary of evaluation metrics. At minimum, this must include
    accuracy, ROC-AUC, and F1 score on a held-out test split. A model should
    not be considered trustworthy for explanation unless its accuracy substantially
    exceeds a majority-class baseline.

    :param model: fitted surrogate estimator
    :param X: feature matrix (may overlap with training data; split internally)
    :param y: binary target series
    :return: dictionary mapping metric name to value, e.g.
             ``{"accuracy": 0.87, "roc_auc": 0.91, "f1": 0.84}``
    """
    # TODO (DD-05): Implement faithfulness evaluation. Use a stratified train/test
    #               split or cross-validation, compute metrics, and return them.
    #               Also compute the majority-class baseline so callers can assess
    #               the improvement.
    raise NotImplementedError(
        "TODO (DD-05): implement faithfulness scoring. "
        "See design-decisions.md DD-05."
    )
