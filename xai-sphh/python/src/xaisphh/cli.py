"""
Command-line interface for the xaisphh analysis pipeline.

Each subcommand corresponds to one stage of the pipeline:

  load      Load raw CSV traces and validate against the schema.
  features  Assemble the model-ready feature matrix.
  yates     Compute reference measures from Yates et al.
  train     Train the surrogate model and evaluate faithfulness.
  explain   Generate SHAP and LIME explanations.
  figures   Produce publication-ready figures for the report.

Run ``python -m xaisphh.cli --help`` or ``xaisphh --help`` for usage.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import pandas as pd


@click.group()
@click.version_option()
def main() -> None:
    """xaisphh: Explainable AI for selection perturbative hyper-heuristics."""


@main.command()
@click.option("--traces", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing CSV trace files written by the Java experiment runner.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for the validated interim dataframe (Parquet format).")
def load(traces: Path, out: Path) -> None:
    """Load and validate raw CSV trace files.

    Reads all CSV traces from TRACES, validates them against the schema defined in
    xaisphh.io.schema, and writes a single Parquet file to OUT for downstream stages.
    """
    from xaisphh.io.loader import load_traces

    click.echo(f"Loading traces from {traces} ...")
    df = load_traces(traces)
    click.echo(f"  Loaded {len(df):,} rows from {traces}.")

    out.mkdir(parents=True, exist_ok=True)
    parquet_path = out / "traces.parquet"
    df.to_parquet(parquet_path, index=False)
    click.echo(f"  Written to {parquet_path}.")


@main.command()
@click.option("--interim", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the Parquet file produced by the 'load' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for the processed feature matrix (Parquet format).")
@click.option("--keep-scores", is_flag=True, default=False,
              help="Include score_* columns in the feature matrix X.")
def features(interim: Path, out: Path, keep_scores: bool) -> None:
    """Assemble the model-ready feature matrix and target.

    Reads the interim Parquet dataframe and writes X (features) and y (target)
    to OUT using xaisphh.features.matrix.build_feature_matrix.
    """
    from xaisphh.features.matrix import build_feature_matrix

    parquet_path = interim / "traces.parquet"
    click.echo(f"Reading {parquet_path} ...")
    df = pd.read_parquet(parquet_path)

    click.echo("Assembling feature matrix ...")
    X, y = build_feature_matrix(df, drop_score_columns=not keep_scores)
    click.echo(f"  X shape: {X.shape}, y shape: {y.shape}.")

    out.mkdir(parents=True, exist_ok=True)
    X.to_parquet(out / "X.parquet", index=False)
    y.to_frame("accepted").to_parquet(out / "y.parquet", index=False)
    click.echo(f"  Written X and y to {out}.")


@main.command()
@click.option("--interim", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the Parquet file produced by the 'load' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for reference measure tables (CSV format).")
def yates(interim: Path, out: Path) -> None:
    """Compute reference measures from Yates et al.

    Computes log returns, percentile bucketing and Spearman footrule distances
    and writes summary tables to OUT.
    """
    from xaisphh.yates.log_returns import compute_log_returns
    from xaisphh.yates.percentiles import percentile_rank, bucket_objectives
    from xaisphh.yates.footrule import heuristic_ranking, footrule_distance

    parquet_path = interim / "traces.parquet"
    click.echo(f"Reading {parquet_path} ...")
    df = pd.read_parquet(parquet_path)

    out.mkdir(parents=True, exist_ok=True)

    # Log returns.
    click.echo("Computing log returns ...")
    df["log_return_computed"] = compute_log_returns(df)
    lr_summary = df.groupby("heuristic_id")["log_return_computed"].describe()
    lr_path = out / "log_returns_by_heuristic.csv"
    lr_summary.to_csv(lr_path)
    click.echo(f"  Written {lr_path}.")

    # Percentile ranks.
    click.echo("Computing percentile ranks ...")
    df["objective_pct_rank"] = percentile_rank(df["objective_after"])
    df["objective_bucket"]   = bucket_objectives(df)
    pct_path = out / "percentile_ranks.csv"
    df[["iteration", "heuristic_id", "objective_after",
        "objective_pct_rank", "objective_bucket"]].to_csv(pct_path, index=False)
    click.echo(f"  Written {pct_path}.")

    # Footrule distance between first half and second half of the run (early vs late search).
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


@main.command()
@click.option("--processed", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the processed feature matrix from the 'features' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for the trained model and faithfulness metrics.")
@click.option("--model-type", default="gradient_boosting",
              type=click.Choice(["gradient_boosting", "random_forest", "logistic_regression"]),
              show_default=True,
              help="Surrogate model family to train.")
@click.option("--seed", default=42, show_default=True,
              help="Random seed for reproducibility.")
def train(processed: Path, out: Path, model_type: str, seed: int) -> None:
    """Train the surrogate model and evaluate its faithfulness.

    Fits the surrogate model on the feature matrix, evaluates faithfulness metrics
    using 5-fold cross-validation, and saves the model and metrics JSON to OUT.
    """
    from xaisphh.surrogate.train import train_surrogate, save_surrogate
    from xaisphh.surrogate.evaluate import faithfulness_score

    click.echo(f"Loading feature matrix from {processed} ...")
    X = pd.read_parquet(processed / "X.parquet")
    y = pd.read_parquet(processed / "y.parquet")["accepted"]

    click.echo(f"Training surrogate ({model_type}, seed={seed}) on {X.shape[0]:,} samples ...")
    model = train_surrogate(X, y, model_type=model_type, random_state=seed)

    click.echo("Evaluating faithfulness (5-fold CV) ...")
    metrics = faithfulness_score(model, X, y)
    click.echo(f"  Accuracy : {metrics['accuracy']:.4f} ± {metrics['accuracy_std']:.4f}")
    click.echo(f"  ROC-AUC  : {metrics['roc_auc']:.4f} ± {metrics['roc_auc_std']:.4f}")
    click.echo(f"  F1       : {metrics['f1']:.4f} ± {metrics['f1_std']:.4f}")
    click.echo(f"  Majority baseline: {metrics['majority_baseline_accuracy']:.4f}")

    out.mkdir(parents=True, exist_ok=True)
    model_path = out / "surrogate.joblib"
    save_surrogate(model, model_path)
    click.echo(f"  Model saved to {model_path}.")

    metrics_path = out / "faithfulness_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    click.echo(f"  Metrics saved to {metrics_path}.")


@main.command()
@click.option("--results", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the trained model produced by the 'train' command.")
@click.option("--processed", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the feature matrix from the 'features' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for SHAP values, LIME explanations and summary tables.")
@click.option("--n-lime-instances", default=5, show_default=True,
              help="Number of individual instances to explain with LIME.")
@click.option("--n-interactions", default=2000, show_default=True,
              help="Max samples used for SHAP interaction values (subsampled for speed).")
def explain(results: Path, processed: Path, out: Path, n_lime_instances: int, n_interactions: int) -> None:
    """Generate SHAP and LIME explanations.

    Loads the surrogate model from RESULTS, computes global SHAP feature importance,
    SHAP interaction values (tree models only), and LIME local explanations for
    selected instances. Writes outputs to OUT.
    """
    from xaisphh.surrogate.train import load_surrogate
    from xaisphh.explain.shap_global import (
        compute_shap_values, global_feature_importance, save_summary_plot,
    )
    from xaisphh.explain.lime_local import explain_instance, save_explanation_plot

    click.echo("Loading model and feature matrix ...")
    model = load_surrogate(results / "surrogate.joblib")
    X = pd.read_parquet(processed / "X.parquet")

    out.mkdir(parents=True, exist_ok=True)

    # Global SHAP.
    click.echo(f"Computing SHAP values for {len(X):,} instances ...")
    shap_values = compute_shap_values(model, X)

    importance = global_feature_importance(shap_values, list(X.columns))
    imp_path = out / "shap_global_importance.csv"
    importance.to_csv(imp_path, index=False)
    click.echo(f"  Feature importance written to {imp_path}.")

    summary_path = out / "shap_summary_plot.pdf"
    save_summary_plot(shap_values, X, summary_path)
    click.echo(f"  Summary plot written to {summary_path}.")

    # SHAP interaction values (tree models only; skip gracefully otherwise).
    try:
        from xaisphh.explain.shap_interactions import (
            compute_interaction_values, save_interaction_heatmap,
        )
        X_inter = X.iloc[:n_interactions] if len(X) > n_interactions else X
        click.echo(f"Computing SHAP interaction values on {len(X_inter):,} samples ...")
        interaction_values = compute_interaction_values(model, X_inter)
        heatmap_path = out / "shap_interaction_heatmap.pdf"
        save_interaction_heatmap(interaction_values, list(X.columns), heatmap_path)
        click.echo(f"  Interaction heatmap written to {heatmap_path}.")
    except TypeError as e:
        click.echo(f"  Skipping interaction values: {e}")

    # LIME local explanations for a handful of representative instances.
    click.echo(f"Generating LIME explanations for {n_lime_instances} instances ...")
    step = max(1, len(X) // n_lime_instances)
    lime_dir = out / "lime"
    lime_dir.mkdir(exist_ok=True)
    for k in range(n_lime_instances):
        idx = k * step
        if idx >= len(X):
            break
        exp = explain_instance(model, X, idx)
        fig_path = lime_dir / f"lime_instance_{idx}.pdf"
        save_explanation_plot(exp, fig_path)
    click.echo(f"  LIME figures written to {lime_dir}.")


@main.command()
@click.option("--results", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing explanation outputs from the 'explain' command.")
@click.option("--interim", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the Parquet trace file from the 'load' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for publication-ready PDF figures.")
def figures(results: Path, interim: Path, out: Path) -> None:
    """Produce publication-ready figures for the report.

    Applies the shared matplotlib style from xaisphh.figures.style and renders
    configured figures to OUT as PDF files:
      - Best-so-far convergence curve per technique and domain.
      - SHAP global importance bar chart.
    """
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

    # SHAP feature importance bar chart.
    imp_path = results / "shap_global_importance.csv"
    if imp_path.exists():
        click.echo("Plotting SHAP importance bar chart ...")
        importance = pd.read_csv(imp_path)
        _plot_importance(importance, out)
    else:
        click.echo(f"  {imp_path} not found; skipping importance chart.")

    click.echo(f"Figures written to {out}.")


# ---------------------------------------------------------------------------
# Private figure helpers
# ---------------------------------------------------------------------------

def _plot_convergence(df: pd.DataFrame, out: Path) -> None:
    """Plot best-so-far over iteration, one line per run, grouped by technique."""
    import matplotlib.pyplot as plt
    from xaisphh.figures.style import apply_style, domain_colour

    apply_style()

    if "run_id" not in df.columns:
        return

    # Group by run_id and plot best_so_far over iteration.
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


def _plot_importance(importance: pd.DataFrame, out: Path) -> None:
    """Horizontal bar chart of mean |SHAP| values."""
    import matplotlib.pyplot as plt
    from xaisphh.figures.style import apply_style, COLOURS

    apply_style()

    top = importance.head(16)
    fig, ax = plt.subplots(figsize=(5.0, max(3.5, len(top) * 0.35)))
    ax.barh(top["feature"][::-1], top["mean_abs_shap"][::-1], color=COLOURS[0])
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title("Global feature importance")
    fig.tight_layout()

    path = out / "shap_importance.pdf"
    fig.savefig(path)
    plt.close(fig)


if __name__ == "__main__":
    main()
