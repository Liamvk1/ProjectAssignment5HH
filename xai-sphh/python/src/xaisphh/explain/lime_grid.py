"""
LIME explanations over a grid of decision points per technique.

Replaces the two hand-picked LIME instances with a systematic grid of
*n_grid* evenly spaced decision points across the budget (using ``feat_progress``
as the axis). Records the conditions (feature names, signs, weights) from each
explanation and summarises condition frequency by progress band.

Item 4.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from lime.lime_tabular import LimeTabularExplainer

from xaisphh.figures.style import apply_style, COLOURS


def lime_grid(
    model: Any,
    X: pd.DataFrame,
    progress: pd.Series,
    n_grid: int = 50,
    num_features: int = 10,
    num_samples: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    """Explain *n_grid* evenly-spaced instances and record condition details.

    Instances are selected by sampling *n_grid* evenly-spaced quantile positions
    across ``progress``. This ensures good coverage across the full search budget
    and is reproducible through *seed*.

    :param model: fitted surrogate estimator
    :param X: feature matrix
    :param progress: series of ``feat_progress`` values aligned with X
    :param n_grid: number of grid points to explain
    :param num_features: max features per LIME explanation
    :param num_samples: perturbation samples per LIME call
    :param seed: random seed for the LIME explainer
    :return: dataframe with columns ``instance_index``, ``progress``,
             ``progress_band``, ``condition``, ``sign``, ``weight``
    """
    feature_names = list(X.columns)
    X_array = X.to_numpy()

    explainer = LimeTabularExplainer(
        training_data=X_array,
        feature_names=feature_names,
        class_names=["rejected", "accepted"],
        mode="classification",
        discretize_continuous=True,
        random_state=seed,
    )

    # Select grid points: quantile-evenly-spaced positions in [0, 1] mapped to
    # actual row indices sorted by progress.
    sorted_idx = np.argsort(progress.to_numpy())
    quantile_positions = np.linspace(0, len(sorted_idx) - 1, n_grid, dtype=int)
    grid_indices = sorted_idx[quantile_positions]

    # Assign progress bands (10 bands).
    progress_values = progress.to_numpy()
    n_bands = 10
    band_edges = np.linspace(0.0, 1.0, n_bands + 1)

    records = []
    for idx in grid_indices:
        instance = X_array[idx]
        prog_val = float(progress_values[idx])

        try:
            exp = explainer.explain_instance(
                data_row=instance,
                predict_fn=model.predict_proba,
                num_features=num_features,
                num_samples=num_samples,
            )
        except Exception:
            continue

        band = int(np.searchsorted(band_edges, prog_val, side="right") - 1)
        band = min(band, n_bands - 1)

        for condition, weight in exp.as_list():
            records.append({
                "instance_index": int(idx),
                "progress":       prog_val,
                "progress_band":  band,
                "condition":      str(condition),
                "sign":           1 if weight > 0 else -1,
                "weight":         float(weight),
            })

    return pd.DataFrame(records)


def condition_frequency_table(grid_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate condition recurrence counts by progress band.

    :param grid_df: dataframe returned by :func:`lime_grid`
    :return: dataframe with columns ``progress_band``, ``condition``,
             ``count``, ``mean_weight``, ``positive_fraction``
    """
    if grid_df.empty:
        return pd.DataFrame(columns=[
            "progress_band", "condition", "count", "mean_weight", "positive_fraction"
        ])

    agg = (
        grid_df.groupby(["progress_band", "condition"])
        .agg(
            count=("weight", "count"),
            mean_weight=("weight", "mean"),
            positive_fraction=("sign", lambda s: (s == 1).mean()),
        )
        .reset_index()
        .sort_values(["progress_band", "count"], ascending=[True, False])
    )
    return agg


def save_condition_frequency_plot(
    freq_df: pd.DataFrame,
    output_path: Path,
    top_n: int = 10,
) -> None:
    """Save a bar chart of top-*n* conditions per progress band.

    :param freq_df: dataframe from :func:`condition_frequency_table`
    :param output_path: destination PDF path
    :param top_n: maximum conditions to show per band
    """
    apply_style()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if freq_df.empty:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No LIME conditions recorded", ha="center", transform=ax.transAxes)
        fig.savefig(output_path)
        plt.close("all")
        return

    bands = sorted(freq_df["progress_band"].unique())
    n_bands = len(bands)
    fig, axes = plt.subplots(1, n_bands, figsize=(4.0 * n_bands, 4.0), sharey=False)
    if n_bands == 1:
        axes = [axes]

    for ax, band in zip(axes, bands):
        sub = freq_df[freq_df["progress_band"] == band].head(top_n)
        colours = [COLOURS[0] if pf >= 0.5 else COLOURS[1]
                   for pf in sub["positive_fraction"]]
        ax.barh(range(len(sub)), sub["count"], color=colours)
        ax.set_yticks(range(len(sub)))
        ax.set_yticklabels(
            [c[:30] for c in sub["condition"]],
            fontsize=6,
        )
        ax.set_title(f"Band {band}", fontsize=8)
        ax.set_xlabel("Count")

    fig.suptitle("LIME condition frequency by progress band", fontsize=10)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close("all")
