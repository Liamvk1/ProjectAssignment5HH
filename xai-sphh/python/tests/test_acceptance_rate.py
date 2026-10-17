"""
Tests for acceptance rate analysis (Item 3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xaisphh.yates.acceptance_rate import acceptance_rate_by_progress


def _sample_df(n: int = 200) -> pd.DataFrame:
    """Build a minimal trace dataframe for acceptance rate testing."""
    rng = np.random.default_rng(42)
    progress = rng.uniform(0, 1, n)
    accepted = (rng.uniform(0, 1, n) > 0.4).astype(bool)
    delta    = rng.standard_normal(n)
    return pd.DataFrame({
        "feat_progress": progress,
        "accepted":      accepted,
        "delta":         delta,
        "technique":     ["SP-CF-LA"] * (n // 2) + ["MP-CF"] * (n - n // 2),
    })


def test_returns_expected_columns() -> None:
    df = _sample_df()
    result = acceptance_rate_by_progress(df, n_bins=10)
    required = {"technique", "progress_bin_centre", "acceptance_rate", "improvement_rate", "count"}
    assert required.issubset(set(result.columns))


def test_rates_are_in_unit_interval() -> None:
    df = _sample_df()
    result = acceptance_rate_by_progress(df, n_bins=10)
    assert (result["acceptance_rate"] >= 0).all()
    assert (result["acceptance_rate"] <= 1).all()
    assert (result["improvement_rate"] >= 0).all()
    assert (result["improvement_rate"] <= 1).all()


def test_bin_count_does_not_exceed_n_bins() -> None:
    df = _sample_df(n=500)
    result = acceptance_rate_by_progress(df, n_bins=20)
    n_unique_bins = result["progress_bin_centre"].nunique()
    assert n_unique_bins <= 20


def test_raises_on_missing_columns() -> None:
    df = pd.DataFrame({"feat_progress": [0.1, 0.5]})
    with pytest.raises(KeyError):
        acceptance_rate_by_progress(df)


def test_output_has_one_row_per_technique_per_bin() -> None:
    """There must be at most one row per (technique, bin) combination."""
    df = _sample_df(n=400)
    result = acceptance_rate_by_progress(df, n_bins=10)
    dupes = result.duplicated(["technique", "progress_bin_centre"])
    assert not dupes.any(), "Duplicate (technique, bin) rows found."
