"""
Tests for log-return computation and heuristic statistics (Item 2).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from xaisphh.yates.log_returns import compute_log_returns, heuristic_stats


# ---------------------------------------------------------------------------
# compute_log_returns
# ---------------------------------------------------------------------------

def _df(before: list, after: list) -> pd.DataFrame:
    """Build a minimal trace dataframe for testing."""
    return pd.DataFrame({
        "objective_before": before,
        "objective_after":  after,
        "heuristic_id":     [0] * len(before),
    })


def test_positive_objectives_compute_log_ratio() -> None:
    df = _df([100.0], [80.0])
    result = compute_log_returns(df)
    assert math.isclose(result.iloc[0], math.log(80.0 / 100.0), rel_tol=1e-9)


def test_non_positive_before_yields_nan() -> None:
    df = _df([0.0, -1.0], [10.0, 10.0])
    result = compute_log_returns(df)
    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])


def test_non_positive_after_yields_nan() -> None:
    df = _df([10.0], [0.0])
    result = compute_log_returns(df)
    assert math.isnan(result.iloc[0])


def test_clipping_suppresses_extreme_values() -> None:
    """Values outside the clip range must be clamped, not discarded."""
    # Very small denominator -> large positive log return.
    df = _df([0.001], [1000.0])
    result_unclipped = compute_log_returns(df, clip_low=float("-inf"), clip_high=float("inf"))
    result_clipped   = compute_log_returns(df, clip_low=-10.0, clip_high=10.0)
    assert result_unclipped.iloc[0] > 10.0
    assert result_clipped.iloc[0] == pytest.approx(10.0)


def test_default_clip_is_applied() -> None:
    """Default call must apply [-10, +10] clipping."""
    df = _df([0.001], [1000.0])
    result = compute_log_returns(df)
    assert result.iloc[0] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# heuristic_stats
# ---------------------------------------------------------------------------

def _trace_df() -> pd.DataFrame:
    """Build a multi-heuristic trace with known log-return characteristics."""
    rng = np.random.default_rng(7)
    before = 100 + rng.standard_normal(200)
    # Heuristic 0: typically slight improvement; heuristic 1: near-zero objectives.
    hids   = [i % 2 for i in range(200)]
    after  = before.copy()
    for i in range(200):
        if hids[i] == 0:
            after[i] = before[i] - rng.uniform(0, 2)
        else:
            after[i] = before[i] + rng.uniform(0, 1)
    return pd.DataFrame({
        "objective_before": before,
        "objective_after":  after,
        "heuristic_id":     hids,
    })


def test_heuristic_stats_returns_correct_columns() -> None:
    df = _trace_df()
    stats, _ = heuristic_stats(df)
    required = {"heuristic_id", "count", "mean", "median", "iqr", "trimmed_mean", "std"}
    assert required.issubset(set(stats.columns))


def test_heuristic_stats_count_matches_valid_rows() -> None:
    """Count must equal the number of rows with both objectives > 0."""
    df = _trace_df()
    stats, _ = heuristic_stats(df)
    total = stats["count"].sum()
    # All objectives in _trace_df are well above zero so all rows should be valid.
    assert total == len(df)


def test_heuristic_stats_diagnostic_flags_divergent_heuristic() -> None:
    """A heuristic with a large mean-median gap must trigger a diagnostic."""
    # Construct a heuristic with a very skewed distribution.
    n = 100
    df = pd.DataFrame({
        "objective_before": [1.0] * n,
        "objective_after":  [0.9999] * (n - 1) + [1000.0],  # one extreme outlier
        "heuristic_id":     [0] * n,
    })
    _, diagnostics = heuristic_stats(df, divergence_factor=2.0)
    assert len(diagnostics) > 0, "Expected a diagnostic for the skewed distribution."
