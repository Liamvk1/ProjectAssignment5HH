"""
Log-return computation and heuristic statistics for objective value sequences.

Replicates the log-return measure used in Yates et al. to characterise the
effectiveness of individual heuristics over time.

Design decision DD-08 and Item 2:
  - Non-positive objectives produce NaN (empty CSV field), not infinity.
  - To prevent blow-up near zero, a configurable clip is applied AFTER the log
    transform. The default clip range is [-10, +10]. This is documented in
    design-decisions.md as an extension of DD-08.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


#: Default clip bounds for log returns. Values outside this range are clamped.
#: Chosen to admit large but physically plausible returns while eliminating
#: near-zero-denominator artefacts. Documented in design-decisions.md DD-08.
DEFAULT_CLIP_LOW:  float = -10.0
DEFAULT_CLIP_HIGH: float =  10.0

#: Factor by which mean may differ from median before a warning is flagged.
DEFAULT_DIVERGENCE_FACTOR: float = 2.0


def compute_log_returns(
    df: pd.DataFrame,
    clip_low:  float = DEFAULT_CLIP_LOW,
    clip_high: float = DEFAULT_CLIP_HIGH,
) -> pd.Series:
    """Compute the log return for each iteration in the trace.

    The log return at iteration t is defined as
    ``log(objective_after_t / objective_before_t)``.
    Rows where either value is non-positive receive ``NaN`` (DD-08).
    Valid log returns are then clipped to [*clip_low*, *clip_high*] to prevent
    near-zero-denominator artefacts from dominating summary statistics.

    :param df: trace dataframe containing ``objective_before`` and ``objective_after``
    :param clip_low: lower bound for clipping; set to ``-inf`` to disable
    :param clip_high: upper bound for clipping; set to ``+inf`` to disable
    :return: series of log returns, aligned to *df*'s index
    :raises KeyError: if required columns are absent
    """
    before = df["objective_before"]
    after  = df["objective_after"]

    # Mask rows where either value is non-positive to avoid log(0) or log(negative).
    valid = (before > 0) & (after > 0)

    log_ret = pd.Series(np.nan, index=df.index, dtype="float64")
    log_ret[valid] = np.log(after[valid] / before[valid])

    # Clip to suppress near-zero-denominator artefacts (see module docstring).
    if clip_low > float("-inf") or clip_high < float("inf"):
        log_ret = log_ret.clip(lower=clip_low, upper=clip_high)

    return log_ret


def heuristic_stats(
    df: pd.DataFrame,
    clip_low:  float = DEFAULT_CLIP_LOW,
    clip_high: float = DEFAULT_CLIP_HIGH,
    trimmed_proportion: float = 0.1,
    divergence_factor: float = DEFAULT_DIVERGENCE_FACTOR,
) -> tuple[pd.DataFrame, list[str]]:
    """Compute per-heuristic log-return summary statistics.

    Returns a dataframe with one row per heuristic ID and the following columns:
    ``count``, ``mean``, ``median``, ``iqr``, ``trimmed_mean``, ``std``.

    Also returns a list of diagnostic messages for heuristics whose mean differs
    from their median by more than *divergence_factor*, which may indicate
    distribution skew caused by near-zero-objective artefacts.

    :param df: trace dataframe
    :param clip_low: lower clip bound passed to :func:`compute_log_returns`
    :param clip_high: upper clip bound passed to :func:`compute_log_returns`
    :param trimmed_proportion: fraction to trim from each tail for the trimmed mean
    :param divergence_factor: flag heuristics where |mean - median| > factor * |median|
    :return: tuple of (stats dataframe, list of diagnostic warning strings)
    """
    log_ret = compute_log_returns(df, clip_low=clip_low, clip_high=clip_high)
    df = df.copy()
    df["log_return_computed"] = log_ret

    rows = []
    for hid, grp in df.groupby("heuristic_id"):
        vals = grp["log_return_computed"].dropna().to_numpy()
        if len(vals) == 0:
            rows.append({
                "heuristic_id": hid,
                "count":        0,
                "mean":         float("nan"),
                "median":       float("nan"),
                "iqr":          float("nan"),
                "trimmed_mean": float("nan"),
                "std":          float("nan"),
            })
            continue

        q25, q75 = float(np.percentile(vals, 25)), float(np.percentile(vals, 75))
        mean_val   = float(np.mean(vals))
        median_val = float(np.median(vals))
        trimmed    = float(scipy_stats.trim_mean(vals, trimmed_proportion))
        rows.append({
            "heuristic_id": int(hid),
            "count":        len(vals),
            "mean":         mean_val,
            "median":       median_val,
            "iqr":          q75 - q25,
            "trimmed_mean": trimmed,
            "std":          float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
        })

    stats_df = pd.DataFrame(rows).sort_values("heuristic_id").reset_index(drop=True)

    # Diagnostics: flag heuristics with suspicious mean-vs-median divergence.
    # When the median is exactly 0 (most log returns are 0, because the objective
    # did not change), ratio-based comparison is meaningless. In that case, flag
    # only when the absolute mean exceeds 0.5 (i.e., a genuine non-trivial shift),
    # which is more interpretable than a ratio that blows up to billions.
    diagnostics: list[str] = []
    for _, row in stats_df.iterrows():
        m, med = row["mean"], row["median"]
        if np.isnan(m) or np.isnan(med):
            continue
        if abs(med) < 1e-6:
            # Median is zero: use absolute mean as the threshold.
            absolute_threshold = 0.5
            if abs(m) > absolute_threshold:
                diagnostics.append(
                    f"Heuristic {int(row['heuristic_id'])}: mean={m:.4f} is "
                    f"notably non-zero while median=0.0 -- possible distribution "
                    f"skew (absolute threshold {absolute_threshold})."
                )
        else:
            if abs(m - med) > divergence_factor * abs(med):
                diagnostics.append(
                    f"Heuristic {int(row['heuristic_id'])}: mean={m:.4f} differs "
                    f"from median={med:.4f} by factor "
                    f"{abs(m - med) / abs(med):.2f} "
                    f"(threshold {divergence_factor}). Possible distribution skew."
                )

    return stats_df, diagnostics
