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

from pathlib import Path

import click


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
    raise NotImplementedError(
        "TODO: call xaisphh.io.loader.load_traces(traces) and write to out as Parquet."
    )


@main.command()
@click.option("--interim", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the Parquet file produced by the 'load' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for the processed feature matrix (Parquet format).")
def features(interim: Path, out: Path) -> None:
    """Assemble the model-ready feature matrix and target.

    Reads the interim Parquet dataframe and writes (X, y) to OUT using
    xaisphh.features.matrix.build_feature_matrix.
    """
    raise NotImplementedError(
        "TODO: call xaisphh.features.matrix.build_feature_matrix and write X, y to out."
    )


@main.command()
@click.option("--processed", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the processed feature matrix from the 'features' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for reference measure tables (CSV format).")
def yates(processed: Path, out: Path) -> None:
    """Compute reference measures from Yates et al.

    Computes log returns, percentile bucketing and Spearman footrule distances
    and writes summary tables to OUT.
    """
    raise NotImplementedError(
        "TODO: call xaisphh.yates modules and write tables to out."
    )


@main.command()
@click.option("--processed", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the processed feature matrix from the 'features' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for the trained model and faithfulness metrics.")
def train(processed: Path, out: Path) -> None:
    """Train the surrogate model and evaluate its faithfulness.

    Fits the surrogate model on the feature matrix, evaluates faithfulness metrics,
    and saves the model and a metrics JSON file to OUT.
    """
    raise NotImplementedError(
        "TODO: call xaisphh.surrogate.train and xaisphh.surrogate.evaluate."
    )


@main.command()
@click.option("--results", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing the trained model produced by the 'train' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for SHAP values, LIME explanations and summary tables.")
def explain(results: Path, out: Path) -> None:
    """Generate SHAP and LIME explanations.

    Loads the surrogate model from RESULTS, computes global SHAP feature importance,
    SHAP interaction values, and LIME local explanations for selected instances.
    Writes outputs to OUT.
    """
    raise NotImplementedError(
        "TODO: call xaisphh.explain.shap_global, shap_interactions, lime_local."
    )


@main.command()
@click.option("--results", required=True, type=click.Path(exists=True, path_type=Path),
              help="Directory containing explanation outputs from the 'explain' command.")
@click.option("--out", required=True, type=click.Path(path_type=Path),
              help="Output directory for publication-ready PDF figures.")
def figures(results: Path, out: Path) -> None:
    """Produce publication-ready figures for the report.

    Applies the shared matplotlib style from xaisphh.figures.style and renders
    all configured figures to OUT as PDF files.
    """
    raise NotImplementedError(
        "TODO: call xaisphh.figures modules and save figures to out."
    )


if __name__ == "__main__":
    main()
