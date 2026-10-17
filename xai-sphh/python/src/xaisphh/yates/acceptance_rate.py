"""
Model-free acceptance rate and improvement rate analysis against search progress.

Bins ``feat_progress`` into equal-width bins and computes, per technique, the
fraction of steps that were accepted and the fraction that were strictly improving.
This provides a model-free check for the exploration-to-exploitation phase claim
previously supported only by two LIME instances (Item 3).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from xaisphh.figures.style import apply_style, COLOURS


def acceptance_rate_by_progress(
    df: pd.DataFrame,
    n_bins: int = 20,
    technique_col: str = "technique",
) -> pd.DataFrame:
    """Compute acceptance rate and improvement rate per progress bin per technique.

    :param df: trace dataframe containing ``feat_progress``, ``accepted``,
               ``delta``, and *technique_col*
    :param n_bins: number of equal-width bins across [0, 1]
    :param technique_col: column name carrying the technique label
    :return: dataframe with columns ``technique``, ``progress_bin_centre``,
             ``acceptance_rate``, ``improvement_rate``, ``count``
    """
    required = {"feat_progress", "accepted", "delta"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"acceptance_rate_by_progress requires columns {required}; "
            f"missing: {missing}"
        )

    # Equal-width bins over [0, 1].
    bin_edges   = np.linspace(0.0, 1.0, n_bins + 1)
    bin_centres = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    labels      = list(range(n_bins))

    df = df.copy()
    df["_progress_bin"] = pd.cut(
        df["feat_progress"],
        bins=bin_edges,
        labels=labels,
        include_lowest=True,
    ).astype("Int64")

    df["_accepted_int"]    = df["accepted"].astype(float)
    df["_improving_int"]   = (df["delta"] < 0).astype(float)

    has_technique = technique_col in df.columns

    if has_technique:
        grp_cols = [technique_col, "_progress_bin"]
    else:
        df["_technique"] = "all"
        grp_cols = ["_technique", "_progress_bin"]

    agg = (
        df.groupby(grp_cols, observed=True)
        .agg(
            count=("_accepted_int", "count"),
            acceptance_rate=("_accepted_int", "mean"),
            improvement_rate=("_improving_int", "mean"),
        )
        .reset_index()
    )

    # Replace bin index with bin centre.
    agg["progress_bin_centre"] = agg["_progress_bin"].map(
        {i: float(bin_centres[i]) for i in range(n_bins)}
    )

    rename = {"_technique": "technique"} if not has_technique else {}
    rename["_progress_bin"] = "progress_bin"
    agg = agg.rename(columns=rename)

    col_order = [
        technique_col if has_technique else "technique",
        "progress_bin",
        "progress_bin_centre",
        "count",
        "acceptance_rate",
        "improvement_rate",
    ]
    return agg[[c for c in col_order if c in agg.columns]]


def save_acceptance_rate_plot(
    rate_df: pd.DataFrame,
    output_path: Path,
    technique_col: str = "technique",
) -> None:
    """Save a line plot of acceptance rate and improvement rate against progress.

    Each technique gets its own line. Acceptance rate and improvement rate are
    plotted on the same axes so their phase relationship is immediately visible.

    :param rate_df: dataframe returned by :func:`acceptance_rate_by_progress`
    :param output_path: destination path for the PDF figure
    :param technique_col: column name carrying the technique label
    """
    apply_style()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    techniques = rate_df[technique_col].unique()
    fig, axes = plt.subplots(
        1, max(1, len(techniques)),
        figsize=(4.5 * max(1, len(techniques)), 3.5),
        sharey=True,
    )
    if len(techniques) == 1:
        axes = [axes]

    for ax, tech in zip(axes, sorted(techniques)):
        sub = rate_df[rate_df[technique_col] == tech].sort_values("progress_bin_centre")
        ax.plot(
            sub["progress_bin_centre"],
            sub["acceptance_rate"],
            label="Acceptance rate",
            color=COLOURS[0],
        )
        ax.plot(
            sub["progress_bin_centre"],
            sub["improvement_rate"],
            label="Improvement rate",
            color=COLOURS[1],
            linestyle="--",
        )
        ax.set_title(tech, fontsize=9)
        ax.set_xlabel("Progress")
        ax.set_ylabel("Rate")
        ax.legend(fontsize=7)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    fig.suptitle("Acceptance and improvement rate vs search progress")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close("all")
