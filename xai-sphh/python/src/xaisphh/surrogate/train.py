"""
Surrogate model training.

Trains a model to approximate the hyper-heuristic's implicit selection policy.
The model is then explained using SHAP and LIME. Its faithfulness to the true
policy determines the validity of the explanations.

Supported model types (DD-05):
  - ``gradient_boosting``  – scikit-learn GradientBoostingClassifier (default)
  - ``random_forest``      – scikit-learn RandomForestClassifier
  - ``logistic_regression`` – scikit-learn LogisticRegression with standard scaling
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


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
    if model_type == "gradient_boosting":
        model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=random_state,
        )
    elif model_type == "random_forest":
        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            min_samples_leaf=5,
            random_state=random_state,
            n_jobs=-1,
        )
    elif model_type == "logistic_regression":
        model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                max_iter=1000,
                random_state=random_state,
                C=1.0,
            )),
        ])
    else:
        raise ValueError(
            f"Unknown model_type '{model_type}'. "
            "Expected one of: 'gradient_boosting', 'random_forest', 'logistic_regression'."
        )

    model.fit(X, y)
    return model


def save_surrogate(model: Any, path: Path) -> None:
    """Serialise the fitted surrogate model to disk using joblib.

    :param model: fitted scikit-learn estimator
    :param path: destination path (conventionally with a ``.joblib`` extension)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def load_surrogate(path: Path) -> Any:
    """Load a previously serialised surrogate model from disk.

    :param path: path to the ``.joblib`` file written by :func:`save_surrogate`
    :return: fitted scikit-learn estimator
    """
    return joblib.load(Path(path))
