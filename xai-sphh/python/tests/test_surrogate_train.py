"""
Tests for surrogate training utilities.

Covers drop_constant_features (Item 1) and the basic train/save/load cycle.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from xaisphh.surrogate.train import (
    drop_constant_features,
    train_surrogate,
    save_surrogate,
    load_surrogate,
)


# ---------------------------------------------------------------------------
# drop_constant_features
# ---------------------------------------------------------------------------

def test_drop_constant_features_removes_zero_variance_columns() -> None:
    """Columns with only one unique value must be dropped."""
    X = pd.DataFrame({
        "feat_a":       [1.0, 2.0, 3.0],
        "feat_b":       [5.0, 5.0, 5.0],   # constant
        "feat_c":       [0.0, 0.0, 0.0],   # constant
        "feat_d":       [1.0, 2.0, 1.0],
    })
    X_filtered, dropped = drop_constant_features(X)
    assert set(dropped) == {"feat_b", "feat_c"}
    assert list(X_filtered.columns) == ["feat_a", "feat_d"]


def test_drop_constant_features_keeps_non_constant_columns() -> None:
    """Columns with more than one unique value must be kept."""
    X = pd.DataFrame({
        "feat_a": [1.0, 2.0, 3.0],
        "feat_b": [4.0, 5.0, 6.0],
    })
    X_filtered, dropped = drop_constant_features(X)
    assert dropped == []
    assert list(X_filtered.columns) == ["feat_a", "feat_b"]


def test_drop_constant_features_all_constant_returns_empty() -> None:
    """If all columns are constant, an empty dataframe is returned."""
    X = pd.DataFrame({"feat_a": [1.0, 1.0], "feat_b": [2.0, 2.0]})
    X_filtered, dropped = drop_constant_features(X)
    assert X_filtered.shape[1] == 0
    assert set(dropped) == {"feat_a", "feat_b"}


def test_drop_constant_features_nan_treated_as_value() -> None:
    """NaN-only columns (one unique value: NaN) must be dropped."""
    X = pd.DataFrame({
        "feat_a": [float("nan"), float("nan"), float("nan")],
        "feat_b": [1.0, 2.0, 3.0],
    })
    X_filtered, dropped = drop_constant_features(X)
    assert "feat_a" in dropped
    assert "feat_b" not in dropped


# ---------------------------------------------------------------------------
# train_surrogate basic smoke tests
# ---------------------------------------------------------------------------

@pytest.fixture
def small_dataset() -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.standard_normal((100, 4)), columns=["f1", "f2", "f3", "f4"])
    y = pd.Series((X["f1"] + rng.standard_normal(100) > 0).astype(int))
    return X, y


def test_train_gradient_boosting(small_dataset: tuple) -> None:
    X, y = small_dataset
    model = train_surrogate(X, y, model_type="gradient_boosting", random_state=42)
    preds = model.predict(X)
    assert len(preds) == len(y)


def test_train_unknown_model_type_raises(small_dataset: tuple) -> None:
    X, y = small_dataset
    with pytest.raises(ValueError, match="Unknown model_type"):
        train_surrogate(X, y, model_type="svm")


def test_save_and_load_surrogate(small_dataset: tuple) -> None:
    X, y = small_dataset
    model = train_surrogate(X, y, random_state=0)
    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as fh:
        path = Path(fh.name)
    save_surrogate(model, path)
    loaded = load_surrogate(path)
    preds_orig   = model.predict(X)
    preds_loaded = loaded.predict(X)
    assert (preds_orig == preds_loaded).all()
