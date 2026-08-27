"""
Surrogate model training.

Trains a model to approximate the hyper-heuristic's implicit selection policy.
The model is then explained using SHAP and LIME. Its faithfulness to the true
policy determines the validity of the explanations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def train_surrogate(
    X: pd.DataFrame,
    y: pd.Series,
    model_type: str = "gradient_boosting",
    random_state: int = 42,
) -> Any:
    """Train a surrogate model on the given feature matrix and target.

    The default model family is gradient-boosted trees (scikit-learn
    ``GradientBoostingClassifier``), chosen because it handles mixed feature
    types, captures non-linear interactions, and is supported natively by SHAP.

    :param X: feature matrix from :func:`xaisphh.features.matrix.build_feature_matrix`
    :param y: binary target series (1 = accepted, 0 = rejected)
    :param model_type: one of ``"gradient_boosting"``, ``"random_forest"``,
                       ``"logistic_regression"``
    :param random_state: random seed for reproducibility
    :return: fitted scikit-learn estimator
    :raises ValueError: if *model_type* is not recognised
    """
    # TODO (DD-05): Implement training. Choose the model family, fit on (X, y),
    #               and return the fitted estimator. Add cross-validation here or
    #               leave it to evaluate.py, depending on the design.
    raise NotImplementedError(
        "TODO (DD-05): implement surrogate model training. "
        "Resolve design-decisions.md DD-05 (model family) first."
    )


def save_surrogate(model: Any, path: Path) -> None:
    """Serialise the fitted surrogate model to disk using joblib.

    :param model: fitted scikit-learn estimator
    :param path: destination path (conventionally with a ``.joblib`` extension)
    """
    raise NotImplementedError("TODO: implement model serialisation using joblib.dump.")


def load_surrogate(path: Path) -> Any:
    """Load a previously serialised surrogate model from disk.

    :param path: path to the ``.joblib`` file written by :func:`save_surrogate`
    :return: fitted scikit-learn estimator
    """
    raise NotImplementedError("TODO: implement model deserialisation using joblib.load.")
