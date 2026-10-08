"""
Command-line interface for the xaisphh analysis pipeline.

Each subcommand corresponds to one stage of the pipeline:

  load      Load raw CSV traces and validate against the schema.
  features  Assemble the model-ready feature matrix.
  yates     Compute reference measures from Yates et al.
  train     Train the surrogate model(s) and evaluate faithfulness.
  explain   Generate SHAP and LIME explanations.
  figures   Produce publication-ready figures for the report.
  stats     Wilcoxon signed-rank tests between technique pairs.

Run ``python -m xaisphh.cli --help`` or ``xaisphh --help`` for usage.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click
import pandas as pd

log = logging.getLogger(__name__)


@click.group()
@click.version_option()
def main() -> None:
    """xaisphh: Explainable AI for selection perturbative hyper-heuristics."""


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

@main.command()
@click.option("--traces", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing CSV trace files and manifest JSON files.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for the validated interim dataframe (Parquet format).")
@click.option("--allow-mixed", is_flag=True, default=False,
              help="Allow mixing stub and real HyFlex runs in one analysis (Item 8).")
def load(traces: Path, out: Path, allow_mixed: bool) -> None:
    """Load and validate raw CSV trace files.

    Reads all CSV traces from TRACES, validates them against the schema defined in
    xaisphh.io.schema, and writes a single Parquet file to OUT for downstream stages.
    Also loads run manifests and writes run_metadata.parquet with per-run attributes.

    Refuses to mix stub and real HyFlex runs unless --allow-mixed is passed.
    """
    from xaisphh.io.loader import load_traces, load_manifests_for_traces, build_run_metadata

    click.echo(f"Loading traces from {traces} ...")
    df = load_traces(traces)
    click.echo(f"  Loaded {len(df):,} rows from {traces}.")

    # Match manifests to trace-file UUIDs by filename stem (the trace run_id is a UUID
    # that differs from the manifest runId, which uses the filename stem).
    manifests = load_manifests_for_traces(traces)
    click.echo(f"  Found {len(manifests)} manifest(s).")

    meta_df = build_run_metadata(df, manifests)

    # Item 8: refuse to mix stub and real runs unless --allow-mixed is passed.
    if not allow_mixed and len(meta_df) > 0 and "stub" in meta_df.columns:
        stub_runs  = set(meta_df.loc[meta_df["stub"] == True,  "run_id"])
        real_runs  = set(meta_df.loc[meta_df["stub"] == False, "run_id"])
        if stub_runs and real_runs:
            raise click.ClickException(
                f"Found both stub runs ({len(stub_runs)}) and real HyFlex runs "
                f"({len(real_runs)}) in the same directory. Pass --allow-mixed to "
                f"proceed anyway. Every figure and table will be labelled accordingly."
            )

    out.mkdir(parents=True, exist_ok=True)
    parquet_path = out / "traces.parquet"
    df.to_parquet(parquet_path, index=False)
    click.echo(f"  Written to {parquet_path}.")

    meta_path = out / "run_metadata.parquet"
    meta_df.to_parquet(meta_path, index=False)
    click.echo(f"  Run metadata written to {meta_path}.")


# ---------------------------------------------------------------------------
# features
# ---------------------------------------------------------------------------

@main.command()
@click.option("--interim", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the Parquet file produced by the 'load' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for the processed feature matrix (Parquet format).")
@click.option("--keep-scores", is_flag=True, default=False,
              help="Include score_* columns in the feature matrix X.")
def features(interim: Path, out: Path, keep_scores: bool) -> None:
    """Assemble the model-ready feature matrix and target.

    Reads the interim Parquet dataframe and writes X (features), y (target),
    and technique (per-row technique label) to OUT.
    """
    from xaisphh.features.matrix import build_feature_matrix
    from xaisphh.io.loader import build_run_metadata

    parquet_path = interim / "traces.parquet"
    click.echo(f"Reading {parquet_path} ...")
    df = pd.read_parquet(parquet_path)

    # Load (or reconstruct) run metadata to get technique labels.
    meta_path = interim / "run_metadata.parquet"
    if meta_path.exists():
        meta_df = pd.read_parquet(meta_path)
        technique_map = dict(zip(meta_df["run_id"], meta_df["technique"]))
        stub_map      = dict(zip(meta_df["run_id"], meta_df["stub"]))
    else:
        # Fall back to parsing technique from run_id.
        from xaisphh.io.loader import technique_from_run_id
        technique_map = {rid: technique_from_run_id(rid) for rid in df["run_id"].unique()}
        stub_map      = {}

    df["technique"] = df["run_id"].map(technique_map)
    if stub_map:
        df["stub"] = df["run_id"].map(stub_map)

    click.echo("Assembling feature matrix ...")
    X, y = build_feature_matrix(df, drop_score_columns=not keep_scores)
    click.echo(f"  X shape: {X.shape}, y shape: {y.shape}.")

    out.mkdir(parents=True, exist_ok=True)
    X.to_parquet(out / "X.parquet", index=False)
    y.to_frame("accepted").to_parquet(out / "y.parquet", index=False)

    # Write technique and stub labels aligned with X/y rows (item 1, 8).
    technique_series = df.loc[X.index, "technique"] if "technique" in df.columns else pd.Series(dtype="string")
    technique_series.to_frame("technique").to_parquet(out / "technique.parquet", index=False)

    if "stub" in df.columns:
        stub_series = df.loc[X.index, "stub"]
        stub_series.to_frame("stub").to_parquet(out / "stub.parquet", index=False)

    click.echo(f"  Written X, y, technique to {out}.")


# ---------------------------------------------------------------------------
# yates
# ---------------------------------------------------------------------------

@main.command()
@click.option("--interim", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the Parquet file produced by the 'load' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for reference measure tables (CSV format).")
@click.option("--clip-low", default=-10.0, show_default=True,
              help="Lower clip bound for log returns (Item 2).")
@click.option("--clip-high", default=10.0, show_default=True,
              help="Upper clip bound for log returns (Item 2).")
@click.option("--divergence-factor", default=2.0, show_default=True,
              help="Flag heuristics whose mean/median differ by this factor (Item 2).")
def yates(
    interim: Path,
    out: Path,
    clip_low: float,
    clip_high: float,
    divergence_factor: float,
) -> None:
    """Compute reference measures from Yates et al.

    Computes log returns with stable clipping, per-heuristic statistics
    (count, mean, median, IQR, trimmed mean), Spearman footrule distances,
    and acceptance/improvement rate vs progress.
    """
    from xaisphh.yates.log_returns import compute_log_returns, heuristic_stats
    from xaisphh.yates.percentiles import percentile_rank, bucket_objectives
    from xaisphh.yates.footrule import heuristic_ranking, footrule_distance
    from xaisphh.yates.acceptance_rate import (
        acceptance_rate_by_progress, save_acceptance_rate_plot,
    )

    parquet_path = interim / "traces.parquet"
    click.echo(f"Reading {parquet_path} ...")
    df = pd.read_parquet(parquet_path)

    # Attach technique labels if available.
    meta_path = interim / "run_metadata.parquet"
    if meta_path.exists():
        meta_df = pd.read_parquet(meta_path)
        technique_map = dict(zip(meta_df["run_id"], meta_df["technique"]))
        df["technique"] = df["run_id"].map(technique_map)

    out.mkdir(parents=True, exist_ok=True)

    # ---- Item 2: richer log-return stats with clipping ----
    click.echo(f"Computing log returns (clip=[{clip_low}, {clip_high}]) ...")
    df["log_return_computed"] = compute_log_returns(df, clip_low=clip_low, clip_high=clip_high)

    stats_df, diagnostics = heuristic_stats(
        df,
        clip_low=clip_low,
        clip_high=clip_high,
        divergence_factor=divergence_factor,
    )
    lr_path = out / "log_returns_by_heuristic.csv"
    stats_df.to_csv(lr_path, index=False)
    click.echo(f"  Written {lr_path}.")

    diag_path = out / "log_return_diagnostics.txt"
    if diagnostics:
        click.echo("  [WARN] Log-return diagnostics:")
        for msg in diagnostics:
            click.echo(f"    {msg}")
        diag_path.write_text("\n".join(diagnostics) + "\n", encoding="utf-8")
        click.echo(f"  Diagnostics written to {diag_path}.")
    else:
        # Always overwrite so a stale file from a previous run is not mistaken
        # for current output.
        diag_path.write_text("", encoding="utf-8")

    # Distribution plots per heuristic (histogram + box plot).
    _plot_heuristic_distributions(df, out)

    # ---- Percentile ranks ----
    click.echo("Computing percentile ranks ...")
    df["objective_pct_rank"] = percentile_rank(df["objective_after"])
    df["objective_bucket"]   = bucket_objectives(df)
    pct_path = out / "percentile_ranks.csv"
    df[["iteration", "heuristic_id", "objective_after",
        "objective_pct_rank", "objective_bucket"]].to_csv(pct_path, index=False)
    click.echo(f"  Written {pct_path}.")

    # ---- Footrule distances ----
    click.echo("Computing footrule distances ...")
    run_ids = df["run_id"].unique()
    footrule_rows = []
    for rid in run_ids:
        run_df = df[df["run_id"] == rid].copy()
        mid = run_df["iteration"].median()
        early = run_df[run_df["iteration"] <= mid]
        late  = run_df[run_df["iteration"] >  mid]
        if early.empty or late.empty:
            continue
        rank_early = heuristic_ranking(early)
        rank_late  = heuristic_ranking(late)
        try:
            dist = footrule_distance(rank_early, rank_late)
        except ValueError:
            dist = float("nan")
        footrule_rows.append({"run_id": rid, "footrule_early_vs_late": dist})

    if footrule_rows:
        footrule_df = pd.DataFrame(footrule_rows)
        fr_path = out / "footrule_distances.csv"
        footrule_df.to_csv(fr_path, index=False)
        click.echo(f"  Written {fr_path}.")
    else:
        click.echo("  No footrule distances computed (insufficient data).")

    # ---- Item 3: acceptance rate vs progress ----
    if "feat_progress" in df.columns and "accepted" in df.columns and "delta" in df.columns:
        click.echo("Computing acceptance rate vs progress ...")
        tech_col = "technique" if "technique" in df.columns else None
        if tech_col is None:
            df["technique"] = "all"
            tech_col = "technique"

        rate_df = acceptance_rate_by_progress(df, n_bins=20, technique_col=tech_col)
        rate_path = out / "acceptance_rate_by_progress.csv"
        rate_df.to_csv(rate_path, index=False)
        click.echo(f"  Written {rate_path}.")

        fig_path = out / "acceptance_rate_by_progress.pdf"
        save_acceptance_rate_plot(rate_df, fig_path, technique_col=tech_col)
        click.echo(f"  Figure written to {fig_path}.")
    else:
        click.echo("  Skipping acceptance rate analysis (feat_progress/accepted/delta not found).")


# ---------------------------------------------------------------------------
# train
# ---------------------------------------------------------------------------

@main.command()
@click.option("--processed", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the feature matrix from the 'features' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for trained model(s) and faithfulness metrics.")
@click.option("--model-type", default="gradient_boosting",
              type=click.Choice(["gradient_boosting", "random_forest", "logistic_regression"]),
              show_default=True, help="Surrogate model family to train.")
@click.option("--seed", default=42, show_default=True, help="Random seed for reproducibility.")
@click.option("--pooled", is_flag=True, default=False,
              help=(
                  "Train a single pooled surrogate on all techniques combined "
                  "(topology classifier). Default: one surrogate per technique (Item 1)."
              ))
@click.option("--ablation", is_flag=True, default=False,
              help="Also run identity/class ablation study per technique (Item 5).")
def train(
    processed: Path,
    out: Path,
    model_type: str,
    seed: int,
    pooled: bool,
    ablation: bool,
) -> None:
    """Train surrogate model(s) and evaluate faithfulness.

    Default: trains one surrogate per technique (--pooled is off). Constant
    features within each technique are automatically dropped and logged.
    Pass --pooled to train a single model on all rows (labelled as a topology
    classifier rather than an acceptance-decision surrogate).
    """
    from xaisphh.surrogate.train import train_surrogate, save_surrogate, drop_constant_features
    from xaisphh.surrogate.evaluate import faithfulness_score

    click.echo(f"Loading feature matrix from {processed} ...")
    X_all = pd.read_parquet(processed / "X.parquet")
    y_all = pd.read_parquet(processed / "y.parquet")["accepted"]

    # Load technique labels.
    technique_path = processed / "technique.parquet"
    if technique_path.exists():
        technique_series = pd.read_parquet(technique_path)["technique"]
    else:
        click.echo("  [WARN] technique.parquet not found; treating all rows as one technique.")
        technique_series = pd.Series(["all"] * len(X_all), name="technique")

    out.mkdir(parents=True, exist_ok=True)

    if pooled:
        _train_pooled(X_all, y_all, model_type, seed, out)
    else:
        _train_per_technique(X_all, y_all, technique_series, model_type, seed, out, ablation)


def _train_pooled(
    X: pd.DataFrame,
    y: pd.Series,
    model_type: str,
    seed: int,
    out: Path,
) -> None:
    """Train a single pooled surrogate (topology classifier)."""
    from xaisphh.surrogate.train import train_surrogate, save_surrogate
    from xaisphh.surrogate.evaluate import faithfulness_score

    click.echo(
        f"[POOLED MODE] Training topology classifier ({model_type}, seed={seed}) "
        f"on {X.shape[0]:,} samples from all techniques combined."
    )
    click.echo(
        "  Note: this model distinguishes technique topology, not acceptance decisions. "
        "Its SHAP values reflect technique identity, not search-state features."
    )

    model = train_surrogate(X, y, model_type=model_type, random_state=seed)
    metrics = faithfulness_score(model, X, y)
    _print_metrics(metrics)

    pooled_dir = out / "pooled"
    pooled_dir.mkdir(parents=True, exist_ok=True)
    from xaisphh.surrogate.train import save_surrogate
    save_surrogate(model, pooled_dir / "surrogate.joblib")
    (pooled_dir / "faithfulness_metrics.json").write_text(
        json.dumps({**metrics, "mode": "topology_classifier"}, indent=2)
    )
    click.echo(f"  Pooled model written to {pooled_dir}.")


def _train_per_technique(
    X_all: pd.DataFrame,
    y_all: pd.Series,
    technique_series: pd.Series,
    model_type: str,
    seed: int,
    out: Path,
    run_ablation: bool,
) -> None:
    """Train one surrogate per technique, drop constant features, optionally run ablation."""
    from xaisphh.surrogate.train import train_surrogate, save_surrogate, drop_constant_features
    from xaisphh.surrogate.evaluate import faithfulness_score

    techniques = sorted(technique_series.unique())
    comparison_rows = []

    for tech in techniques:
        mask = technique_series == tech
        X_tech = X_all.loc[mask.values].reset_index(drop=True)
        y_tech = y_all.loc[mask.values].reset_index(drop=True)

        click.echo(f"\n--- Technique: {tech} ({len(X_tech):,} samples) ---")

        # Drop constant features.
        X_filtered, dropped = drop_constant_features(X_tech)
        if dropped:
            click.echo(f"  Dropped {len(dropped)} constant feature(s): {dropped}")

        if X_filtered.shape[1] == 0:
            click.echo(f"  [WARN] All features are constant for {tech}; skipping.")
            continue

        click.echo(f"  Training {model_type} (seed={seed}) on {X_filtered.shape[1]} features ...")
        model = train_surrogate(X_filtered, y_tech, model_type=model_type, random_state=seed)

        metrics = faithfulness_score(model, X_filtered, y_tech)
        _print_metrics(metrics)

        tech_dir = out / tech
        tech_dir.mkdir(parents=True, exist_ok=True)
        save_surrogate(model, tech_dir / "surrogate.joblib")
        meta = {
            **metrics,
            "technique":       tech,
            "n_samples":       len(X_tech),
            "n_features_used": X_filtered.shape[1],
            "dropped_features": dropped,
            "mode":            "per_technique_surrogate",
        }
        (tech_dir / "faithfulness_metrics.json").write_text(json.dumps(meta, indent=2))
        click.echo(f"  Model written to {tech_dir}.")

        # Collect per-technique SHAP importance for comparison table (computed in explain).
        comparison_rows.append({
            "technique":       tech,
            "accuracy":        metrics["accuracy"],
            "roc_auc":         metrics["roc_auc"],
            "majority_baseline": metrics["majority_baseline_accuracy"],
            "n_features_used": X_filtered.shape[1],
            "dropped_features": "; ".join(dropped),
        })

        # Optional ablation (Item 5).
        if run_ablation:
            click.echo(f"  Running identity/class ablation for {tech} ...")
            from xaisphh.surrogate.ablation import run_ablation as do_ablation
            abl_df = do_ablation(X_filtered, y_tech, model_type=model_type, random_state=seed)
            abl_path = tech_dir / "ablation_results.csv"
            abl_df.to_csv(abl_path, index=False)
            click.echo(f"  Ablation results written to {abl_path}.")
            for _, row in abl_df.iterrows():
                click.echo(
                    f"    {row['variant']:20s}: "
                    f"accuracy={row['accuracy']:.4f}, "
                    f"roc_auc={row['roc_auc']:.4f}"
                )

    # Write comparison table.
    if comparison_rows:
        comp_df = pd.DataFrame(comparison_rows)
        comp_path = out / "technique_comparison.csv"
        comp_df.to_csv(comp_path, index=False)
        click.echo(f"\nTechnique comparison table written to {comp_path}.")


# ---------------------------------------------------------------------------
# explain
# ---------------------------------------------------------------------------

@main.command()
@click.option("--results", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing trained model(s) from the 'train' command.")
@click.option("--processed", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the feature matrix from the 'features' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for SHAP values, LIME explanations and summary tables.")
@click.option("--n-lime-grid", default=50, show_default=True,
              help="Number of evenly-spaced LIME grid points per technique (Item 4).")
@click.option("--n-interactions", default=2000, show_default=True,
              help="Max samples used for SHAP interaction values.")
@click.option("--pooled", is_flag=True, default=False,
              help="Explain the pooled topology-classifier model instead of per-technique models.")
@click.option("--seed", default=42, show_default=True, help="Random seed for LIME grid.")
def explain(
    results: Path,
    processed: Path,
    out: Path,
    n_lime_grid: int,
    n_interactions: int,
    pooled: bool,
    seed: int,
) -> None:
    """Generate SHAP and LIME explanations.

    Default: per-technique explanations from per-technique surrogates (Item 1).
    Pass --pooled to explain the pooled topology-classifier model.
    LIME is run over a systematic grid of evenly-spaced decision points (Item 4).
    """
    from xaisphh.surrogate.train import load_surrogate, drop_constant_features
    from xaisphh.explain.shap_global import (
        compute_shap_values, global_feature_importance, save_summary_plot,
    )
    from xaisphh.explain.lime_grid import lime_grid, condition_frequency_table

    click.echo(f"Loading feature matrix from {processed} ...")
    X_all = pd.read_parquet(processed / "X.parquet")

    technique_path = processed / "technique.parquet"
    if technique_path.exists():
        technique_series = pd.read_parquet(technique_path)["technique"]
    else:
        technique_series = pd.Series(["all"] * len(X_all), name="technique")

    out.mkdir(parents=True, exist_ok=True)

    if pooled:
        _explain_pooled(results, X_all, out, n_interactions)
        return

    # Per-technique explanations.
    techniques = sorted(technique_series.unique())
    shap_comparison_rows: list[dict] = []

    for tech in techniques:
        model_path = results / tech / "surrogate.joblib"
        if not model_path.exists():
            click.echo(f"  [WARN] No model found for {tech} at {model_path}; skipping.")
            continue

        mask = technique_series == tech
        X_tech = X_all.loc[mask.values].reset_index(drop=True)

        # Re-apply the same constant-feature drop used during training.
        from xaisphh.surrogate.train import drop_constant_features
        X_tech, _ = drop_constant_features(X_tech)

        click.echo(f"\n--- Explaining: {tech} ({len(X_tech):,} samples) ---")
        model = load_surrogate(model_path)

        tech_out = out / tech
        tech_out.mkdir(parents=True, exist_ok=True)

        # Global SHAP.
        click.echo(f"  Computing SHAP values ...")
        shap_values = compute_shap_values(model, X_tech)
        importance  = global_feature_importance(shap_values, list(X_tech.columns))
        importance.to_csv(tech_out / "shap_global_importance.csv", index=False)

        save_summary_plot(shap_values, X_tech, tech_out / "shap_summary_plot.pdf")
        click.echo(f"  SHAP importance written to {tech_out}.")

        # SHAP interaction values.
        try:
            from xaisphh.explain.shap_interactions import (
                compute_interaction_values, save_interaction_heatmap,
            )
            X_inter = X_tech.iloc[:n_interactions] if len(X_tech) > n_interactions else X_tech
            interaction_values = compute_interaction_values(model, X_inter)
            save_interaction_heatmap(
                interaction_values, list(X_tech.columns),
                tech_out / "shap_interaction_heatmap.pdf",
            )
            click.echo(f"  Interaction heatmap written to {tech_out}.")
        except TypeError as exc:
            click.echo(f"  Skipping interaction values: {exc}")

        # LIME grid (Item 4).
        if "feat_progress" in X_tech.columns:
            progress = X_tech["feat_progress"]
        else:
            progress = pd.Series(
                [i / max(1, len(X_tech) - 1) for i in range(len(X_tech))],
                name="feat_progress",
            )

        click.echo(f"  Running LIME grid ({n_lime_grid} points) ...")
        grid_df = lime_grid(
            model, X_tech, progress,
            n_grid=n_lime_grid,
            seed=seed,
        )
        grid_df.to_csv(tech_out / "lime_grid.csv", index=False)

        freq_df = condition_frequency_table(grid_df)
        freq_df.to_csv(tech_out / "lime_condition_frequency.csv", index=False)

        from xaisphh.explain.lime_grid import save_condition_frequency_plot
        save_condition_frequency_plot(freq_df, tech_out / "lime_condition_frequency.pdf")
        click.echo(f"  LIME grid written to {tech_out}.")

        # Collect for comparison table.
        for _, row in importance.head(10).iterrows():
            shap_comparison_rows.append({
                "technique":     tech,
                "feature":       row["feature"],
                "mean_abs_shap": row["mean_abs_shap"],
            })

    # Cross-technique SHAP comparison table (Item 1).
    if shap_comparison_rows:
        comp_df = pd.DataFrame(shap_comparison_rows)
        comp_path = out / "shap_comparison_by_technique.csv"
        comp_df.to_csv(comp_path, index=False)
        click.echo(f"\nCross-technique SHAP comparison written to {comp_path}.")


def _explain_pooled(results: Path, X_all: pd.DataFrame, out: Path, n_interactions: int) -> None:
    """Explain the pooled topology-classifier model."""
    from xaisphh.surrogate.train import load_surrogate
    from xaisphh.explain.shap_global import (
        compute_shap_values, global_feature_importance, save_summary_plot,
    )

    model_path = results / "pooled" / "surrogate.joblib"
    if not model_path.exists():
        raise click.ClickException(
            f"Pooled model not found at {model_path}. "
            "Run 'train --pooled' first."
        )

    click.echo("[POOLED MODE] Explaining topology-classifier model.")
    model = load_surrogate(model_path)

    pooled_out = out / "pooled"
    pooled_out.mkdir(parents=True, exist_ok=True)

    shap_values = compute_shap_values(model, X_all)
    importance  = global_feature_importance(shap_values, list(X_all.columns))
    importance.to_csv(pooled_out / "shap_global_importance.csv", index=False)
    save_summary_plot(shap_values, X_all, pooled_out / "shap_summary_plot.pdf")
    click.echo(f"  Pooled SHAP outputs written to {pooled_out}.")


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------

@main.command()
@click.option("--results", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing explanation outputs from the 'explain' command.")
@click.option("--interim", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the Parquet trace file from the 'load' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for publication-ready PDF figures.")
def figures(results: Path, interim: Path, out: Path) -> None:
    """Produce publication-ready figures for the report."""
    import matplotlib.pyplot as plt
    from xaisphh.figures.style import apply_style, domain_colour

    apply_style()
    out.mkdir(parents=True, exist_ok=True)

    # Convergence curves from the raw trace data.
    parquet_path = interim / "traces.parquet"
    if parquet_path.exists():
        click.echo("Plotting convergence curves ...")
        df = pd.read_parquet(parquet_path)
        _plot_convergence(df, out)
    else:
        click.echo(f"  {parquet_path} not found; skipping convergence curves.")

    # SHAP feature importance bar chart (try per-technique first, then pooled).
    _plot_available_shap_importance(results, out)

    click.echo(f"Figures written to {out}.")


# ---------------------------------------------------------------------------
# stats (Item 7)
# ---------------------------------------------------------------------------

@main.command()
@click.option("--objectives", required=True, type=click.Path(exists=True, path_type=Path),
              help="CSV with columns technique, domain, instance, seed, final_objective.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output path for the Wilcoxon results CSV.")
def stats(objectives: Path, out: Path) -> None:
    """Wilcoxon signed-rank tests between technique pairs, per domain, with Holm correction.

    Reads final objectives from a CSV and performs pairwise Wilcoxon signed-rank
    tests between all technique pairs within each domain. Applies a Holm correction
    across all pairs within each domain.
    """
    from xaisphh.scripts.wilcoxon_stats import wilcoxon_pairwise

    click.echo(f"Loading objectives from {objectives} ...")
    df = pd.read_csv(objectives)

    click.echo("Running Wilcoxon signed-rank tests ...")
    results_df = wilcoxon_pairwise(df)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(out, index=False)
    click.echo(f"Written {len(results_df)} rows to {out}.")

    n_reject = results_df["reject_holm"].sum()
    click.echo(f"Significant pairs (Holm p < 0.05): {n_reject} / {len(results_df)}.")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@main.command()
@click.option("--interim",      required=True, type=click.Path(exists=True, path_type=Path),
              help="data/interim directory (run_metadata.parquet).")
@click.option("--processed",    required=True, type=click.Path(exists=True, path_type=Path),
              help="data/processed directory (contains yates/ subdirectory).")
@click.option("--models",       required=True, type=click.Path(exists=True, path_type=Path),
              help="results/models directory.")
@click.option("--explanations", required=True, type=click.Path(exists=True, path_type=Path),
              help="results/explanations directory.")
@click.option("--out",          required=True, type=click.Path(path_type=Path),
              help="Output PDF file path (e.g. results/report.pdf).")
def report(interim: Path, processed: Path, models: Path,
           explanations: Path, out: Path) -> None:
    """Generate a multi-page PDF report of all pipeline outputs.

    Always writes to --out (the 'latest' copy) and also saves a timestamped
    copy alongside it so previous reports are not lost.
    """
    from xaisphh.report.generate import generate_report
    import shutil
    import matplotlib
    matplotlib.use("Agg")

    out = Path(out)
    click.echo("Generating report ...")
    generate_report(
        interim_dir      = interim,
        processed_dir    = processed,
        models_dir       = models,
        explanations_dir = explanations,
        out_path         = out,
    )
    click.echo(f"  Report written to {out}.")

    # Save a timestamped copy so previous runs are preserved.
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    stamped = out.parent / f"{out.stem}_{ts}{out.suffix}"
    shutil.copy2(out, stamped)
    click.echo(f"  Timestamped copy saved to {stamped}.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _print_metrics(metrics: dict) -> None:
    click.echo(f"  Accuracy : {metrics['accuracy']:.4f} +/- {metrics['accuracy_std']:.4f}")
    click.echo(f"  ROC-AUC  : {metrics['roc_auc']:.4f} +/- {metrics['roc_auc_std']:.4f}")
    click.echo(f"  F1       : {metrics['f1']:.4f} +/- {metrics['f1_std']:.4f}")
    click.echo(f"  Majority baseline: {metrics['majority_baseline_accuracy']:.4f}")


def _plot_convergence(df: pd.DataFrame, out: Path) -> None:
    """Plot best-so-far over iteration, one line per run, grouped by technique."""
    import matplotlib.pyplot as plt
    from xaisphh.figures.style import apply_style

    apply_style()

    if "run_id" not in df.columns:
        return

    fig, ax = plt.subplots()
    for i, (rid, run_df) in enumerate(df.groupby("run_id")):
        run_df = run_df.sort_values("iteration")
        ax.plot(
            run_df["iteration"],
            run_df["best_so_far"],
            alpha=0.6,
            linewidth=0.8,
            label=str(rid)[:8] if i < 10 else None,
        )

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Best objective")
    ax.set_title("Convergence (best-so-far)")
    if len(df["run_id"].unique()) <= 10:
        ax.legend(fontsize=7)

    path = out / "convergence.pdf"
    fig.savefig(path)
    plt.close(fig)


def _plot_available_shap_importance(results: Path, out: Path) -> None:
    """Plot SHAP importance bar charts for whatever models are available."""
    import matplotlib.pyplot as plt
    from xaisphh.figures.style import apply_style, COLOURS

    apply_style()

    # Try per-technique models first.
    per_tech_found = False
    for tech_dir in sorted(results.iterdir()):
        imp_path = tech_dir / "shap_global_importance.csv"
        if imp_path.exists():
            per_tech_found = True
            importance = pd.read_csv(imp_path)
            _plot_importance(importance, out, title_suffix=f" ({tech_dir.name})")

    # Fall back to pooled.
    pooled_imp = results / "pooled" / "shap_global_importance.csv"
    if not per_tech_found and pooled_imp.exists():
        importance = pd.read_csv(pooled_imp)
        _plot_importance(importance, out, title_suffix=" (pooled topology classifier)")

    # Also the flat shap_global_importance.csv at results root for backward compat.
    flat_imp = results / "shap_global_importance.csv"
    if flat_imp.exists() and not per_tech_found:
        importance = pd.read_csv(flat_imp)
        _plot_importance(importance, out, title_suffix="")


def _plot_importance(importance: pd.DataFrame, out: Path, title_suffix: str = "") -> None:
    """Horizontal bar chart of mean |SHAP| values."""
    import matplotlib.pyplot as plt
    from xaisphh.figures.style import COLOURS

    top = importance.head(16)
    fig, ax = plt.subplots(figsize=(5.0, max(3.5, len(top) * 0.35)))
    ax.barh(top["feature"][::-1], top["mean_abs_shap"][::-1], color=COLOURS[0])
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title(f"Global feature importance{title_suffix}")
    fig.tight_layout()

    safe_suffix = title_suffix.strip().replace(" ", "_").replace("(", "").replace(")", "")
    path = out / f"shap_importance{safe_suffix}.pdf"
    fig.savefig(path)
    plt.close(fig)


def _plot_heuristic_distributions(df: pd.DataFrame, out: Path) -> None:
    """Save histogram + box plot for each heuristic's log return distribution."""
    import matplotlib.pyplot as plt
    from xaisphh.figures.style import apply_style, COLOURS
    from xaisphh.yates.log_returns import compute_log_returns

    apply_style()

    if "log_return_computed" not in df.columns:
        return

    dist_dir = out / "heuristic_distributions"
    dist_dir.mkdir(exist_ok=True)

    heuristic_ids = sorted(df["heuristic_id"].unique())
    n_h = len(heuristic_ids)
    if n_h == 0:
        return

    # One multi-panel figure: rows = heuristics, cols = histogram + box.
    n_cols = 2
    fig, axes = plt.subplots(n_h, n_cols, figsize=(6, 2.2 * n_h), squeeze=False)

    for row_idx, hid in enumerate(heuristic_ids):
        vals = df.loc[df["heuristic_id"] == hid, "log_return_computed"].dropna().to_numpy()

        ax_hist = axes[row_idx, 0]
        ax_box  = axes[row_idx, 1]

        if len(vals) > 0:
            ax_hist.hist(vals, bins=40, color=COLOURS[0], edgecolor="none", alpha=0.8)
            ax_box.boxplot(vals, orientation="horizontal", patch_artist=True,
                           boxprops=dict(facecolor=COLOURS[0], alpha=0.7))
        ax_hist.set_title(f"h{hid} histogram", fontsize=8)
        ax_box.set_title(f"h{hid} box", fontsize=8)
        ax_hist.set_xlabel("Log return")
        ax_box.set_xlabel("Log return")

    fig.suptitle("Per-heuristic log-return distributions", fontsize=9)
    fig.tight_layout()
    fig.savefig(dist_dir / "all_heuristics.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
