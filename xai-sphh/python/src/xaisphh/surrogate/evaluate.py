"""
Surrogate model faithfulness evaluation.

A surrogate model that does not accurately approximate the hyper-heuristic's
decisions explains nothing meaningful. This module computes faithfulness metrics
to quantify how well the surrogate matches the observed decisions before any
SHAP or LIME analysis is performed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_validate


def faithfulness_score(
    model: Any,
    X: pd.DataFrame,
    y: pd.Series,
) -> dict[str, float]:
    """Compute faithfulness metrics for the surrogate model.

    Uses 5-fold stratified cross-validation so the reported metrics are not
    optimistic estimates from training-set performance. Also computes the
    majority-class baseline accuracy so callers can assess the improvement.

    :param model: fitted surrogate estimator
    :param X: feature matrix (may overlap with training data; split internally)
    :param y: binary target series
    :return: dictionary mapping metric name to value, including:
             ``accuracy``, ``roc_auc``, ``f1``, ``majority_baseline_accuracy``
    """
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    scoring = {
        "accuracy": "accuracy",
        "roc_auc":  "roc_auc",
        "f1":       "f1",
    }

    cv_results = cross_validate(model, X, y, cv=cv, scoring=scoring)

    majority_class_rate = float(max(y.mean(), 1 - y.mean()))

    return {
        "accuracy":                  float(np.mean(cv_results["test_accuracy"])),
        "accuracy_std":              float(np.std(cv_results["test_accuracy"])),
        "roc_auc":                   float(np.mean(cv_results["test_roc_auc"])),
        "roc_auc_std":               float(np.std(cv_results["test_roc_auc"])),
        "f1":                        float(np.mean(cv_results["test_f1"])),
        "f1_std":                    float(np.std(cv_results["test_f1"])),
        "majority_baseline_accuracy": majority_class_rate,
    }
