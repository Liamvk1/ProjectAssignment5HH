"""
Identity vs class feature ablation study.

Trains three surrogate variants per technique:
  1. all features (full model)
  2. identity features removed (feat_last_h1, feat_last_h2, feat_last_h3)
  3. class features removed (feat_last_class1, feat_last_class2, feat_last_class3)

Reporting accuracy and ROC-AUC for each variant separates redundancy from
informativeness: if removing a feature group does not hurt accuracy, the remaining
features already encode the same information.

Item 5.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from xaisphh.surrogate.train import train_surrogate
from xaisphh.surrogate.evaluate import faithfulness_score


#: Feature columns that encode heuristic identity (index).
IDENTITY_FEATURES: list[str] = ["feat_last_h1", "feat_last_h2", "feat_last_h3"]

#: Feature columns that encode heuristic class (type ordinal).
CLASS_FEATURES: list[str] = [
    "feat_last_class1", "feat_last_class2", "feat_last_class3"
]


def run_ablation(
    X: pd.DataFrame,
    y: pd.Series,
    model_type: str = "gradient_boosting",
    random_state: int = 42,
) -> pd.DataFrame:
    """Train three surrogate variants and report faithfulness metrics for each.

    :param X: feature matrix (already filtered for one technique)
    :param y: binary target series
    :param model_type: surrogate model family to use for all three variants
    :param random_state: random seed for reproducibility
    :return: dataframe with columns ``variant``, ``accuracy``, ``accuracy_std``,
             ``roc_auc``, ``roc_auc_std``, ``f1``, ``f1_std``,
             ``majority_baseline_accuracy``, ``n_features``
    """
    variants: dict[str, pd.DataFrame] = {
        "full":            X,
        "no_identity":     X.drop(columns=[c for c in IDENTITY_FEATURES if c in X.columns]),
        "no_class":        X.drop(columns=[c for c in CLASS_FEATURES    if c in X.columns]),
    }

    rows = []
    for variant_name, X_var in variants.items():
        if X_var.shape[1] == 0:
            rows.append({
                "variant":                    variant_name,
                "n_features":                 0,
                "accuracy":                   float("nan"),
                "accuracy_std":               float("nan"),
                "roc_auc":                    float("nan"),
                "roc_auc_std":                float("nan"),
                "f1":                         float("nan"),
                "f1_std":                     float("nan"),
                "majority_baseline_accuracy": float(max(y.mean(), 1 - y.mean())),
            })
            continue

        model = train_surrogate(X_var, y, model_type=model_type, random_state=random_state)
        metrics = faithfulness_score(model, X_var, y)
        rows.append({
            "variant":    variant_name,
            "n_features": X_var.shape[1],
            **metrics,
        })

    return pd.DataFrame(rows)
