"""
Multi-page PDF report generator for xai-sphh pipeline outputs.

Reads the artefacts produced by the load, features, yates, train, and explain
pipeline stages and assembles them into a single self-contained PDF that can be
submitted alongside the assignment write-up.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

# Matches stale UUID-named directories left over from pre-fix runs.
_UUID = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)

HEADER_COLOUR  = "#2c3e50"
ROW_ALT_COLOUR = "#f0f4f8"
ACCENT         = "#2980b9"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _is_uuid(name: str) -> bool:
    return bool(_UUID.match(name))


def _section_header(pdf: PdfPages, number: str, title: str, subtitle: str = "") -> None:
    """Dark-background section divider page."""
    fig = plt.figure(figsize=(11.69, 8.27))
    ax  = fig.add_subplot(111)
    ax.axis("off")
    ax.set_facecolor(HEADER_COLOUR)
    fig.patch.set_facecolor(HEADER_COLOUR)
    ax.text(0.5, 0.60, number, transform=ax.transAxes,
            ha="center", va="center", fontsize=16, color="#7fb3d3")
    ax.text(0.5, 0.50, title, transform=ax.transAxes,
            ha="center", va="center", fontsize=22, fontweight="bold", color="white")
    if subtitle:
        ax.text(0.5, 0.38, subtitle, transform=ax.transAxes,
                ha="center", va="center", fontsize=12, color="#bdc3c7")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _df_to_page(pdf: PdfPages, title: str, df: pd.DataFrame,
                col_widths: list[float] | None = None,
                fontsize: int = 8, max_rows: int = 40) -> None:
    """Render a DataFrame as a styled table, paginating if needed."""
    if df.empty:
        return

    for chunk_start in range(0, len(df), max_rows):
        chunk = df.iloc[chunk_start : chunk_start + max_rows].copy()

        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")

        page_title = title
        if len(df) > max_rows:
            end = min(chunk_start + max_rows, len(df))
            page_title = f"{title}  (rows {chunk_start + 1}-{end} of {len(df)})"
        ax.set_title(page_title, fontsize=11, fontweight="bold", loc="left", pad=12)

        col_labels = list(chunk.columns)
        cell_data  = []
        for _, row in chunk.iterrows():
            formatted = []
            for v in row:
                if isinstance(v, float) and not np.isnan(v):
                    formatted.append(f"{v:.4f}" if abs(v) < 1e5 else f"{v:.3e}")
                else:
                    formatted.append(str(v))
            cell_data.append(formatted)

        cw = col_widths or [1.0 / max(len(col_labels), 1)] * len(col_labels)

        tbl = ax.table(
            cellText=cell_data,
            colLabels=col_labels,
            colWidths=cw,
            loc="center",
            cellLoc="left",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(fontsize)
        tbl.scale(1, 1.5)

        # Header row styling
        for j in range(len(col_labels)):
            cell = tbl[0, j]
            cell.set_facecolor(HEADER_COLOUR)
            cell.set_text_props(color="white", fontweight="bold")

        # Alternating row shading
        for i in range(1, len(chunk) + 1):
            bg = ROW_ALT_COLOUR if i % 2 == 0 else "white"
            for j in range(len(col_labels)):
                tbl[i, j].set_facecolor(bg)

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _cover_page(pdf: PdfPages, run_meta: pd.DataFrame | None) -> None:
    fig = plt.figure(figsize=(11.69, 8.27))
    ax  = fig.add_subplot(111)
    ax.axis("off")

    # Decorative top bar
    ax.add_patch(plt.Rectangle((0, 0.88), 1, 0.12,
                                transform=ax.transAxes, color=HEADER_COLOUR, zorder=0))

    ax.text(0.5, 0.935, "xai-sphh  Pipeline Results Report",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=20, fontweight="bold", color="white")

    ax.text(0.5, 0.82,
            "Explainable AI for Cross-Domain Selection Perturbative Hyper-Heuristics",
            transform=ax.transAxes, ha="center", va="top",
            fontsize=12, color="#555")

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    ax.text(0.5, 0.75, f"Generated: {now}",
            transform=ax.transAxes, ha="center", va="top", fontsize=10, color="#888")

    if run_meta is not None and not run_meta.empty:
        techniques = sorted(run_meta["technique"].unique())
        domains    = sorted(run_meta["domain"].unique()) if "domain" in run_meta.columns else []
        n_stub     = int(run_meta["stub"].sum()) if "stub" in run_meta.columns else "?"
        n_total    = len(run_meta)

        summary = [
            ("Runs in dataset",  str(n_total)),
            ("Techniques",       ", ".join(techniques)),
            ("Domains",          ", ".join(domains) if domains else "N/A"),
            ("Real / Stub runs", f"{n_total - n_stub} / {n_stub}"),
        ]
        y = 0.65
        for label, value in summary:
            ax.text(0.12, y, f"{label}:", transform=ax.transAxes, va="top",
                    fontsize=10, fontweight="bold", color=HEADER_COLOUR)
            ax.text(0.38, y, value, transform=ax.transAxes, va="top",
                    fontsize=10, color="#333")
            y -= 0.055

    # Contents list
    ax.text(0.12, 0.36, "Contents", transform=ax.transAxes, va="top",
            fontsize=11, fontweight="bold", color=HEADER_COLOUR)
    sections = [
        "1.  Run Metadata",
        "2.  Log-Return Statistics by Heuristic",
        "3.  Acceptance Rate vs Search Progress",
        "4.  Technique Comparison (Surrogate Faithfulness)",
        "5.  Ablation Study -- Identity vs Class Features",
        "6.  SHAP Cross-Technique Feature Importance Heatmap",
        "7.  Per-Technique SHAP Importance Charts",
        "8.  LIME Condition Frequency Tables",
    ]
    y = 0.29
    for s in sections:
        ax.text(0.15, y, s, transform=ax.transAxes, va="top", fontsize=9.5, color="#444")
        y -= 0.038

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _run_metadata_section(pdf: PdfPages, interim_dir: Path) -> None:
    path = interim_dir / "run_metadata.parquet"
    if not path.exists():
        return
    df = pd.read_parquet(path)
    _df_to_page(pdf, "Run Metadata", df)


def _log_returns_section(pdf: PdfPages, yates_dir: Path) -> None:
    lr_path = yates_dir / "log_returns_by_heuristic.csv"
    if lr_path.exists():
        df = pd.read_csv(lr_path)
        _df_to_page(pdf, "Log-Return Statistics by Heuristic", df)

    diag_path = yates_dir / "log_return_diagnostics.txt"
    if diag_path.exists() and diag_path.stat().st_size > 0:
        text = diag_path.read_text(encoding="utf-8").strip()
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        ax.set_title("Log-Return Diagnostics", fontsize=11, fontweight="bold",
                     loc="left", pad=12)
        ax.text(0.02, 0.90, text, transform=ax.transAxes, va="top",
                fontsize=8.5, fontfamily="monospace",
                bbox=dict(boxstyle="round", facecolor="#fff3cd", alpha=0.85))
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
    else:
        # Brief note confirming no diagnostics were raised
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        ax.axis("off")
        ax.set_title("Log-Return Diagnostics", fontsize=11, fontweight="bold",
                     loc="left", pad=12)
        ax.text(0.02, 0.90,
                "No divergent heuristics detected.\n"
                "All per-heuristic mean/median differences are within the configured threshold.",
                transform=ax.transAxes, va="top", fontsize=10,
                bbox=dict(boxstyle="round", facecolor="#d4edda", alpha=0.85))
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def _acceptance_rate_section(pdf: PdfPages, yates_dir: Path) -> None:
    csv_path = yates_dir / "acceptance_rate_by_progress.csv"
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path)
    if df.empty or "technique" not in df.columns:
        return

    techniques = sorted(df["technique"].unique())
    ncols = min(2, len(techniques))
    nrows = (len(techniques) + ncols - 1) // ncols

    fig, axes = plt.subplots(nrows, ncols, figsize=(11.69, 8.27), squeeze=False)
    fig.suptitle("Acceptance Rate and Improvement Rate vs Search Progress",
                 fontsize=12, fontweight="bold")

    colours = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    for idx, tech in enumerate(techniques):
        row, col = divmod(idx, ncols)
        ax  = axes[row][col]
        progress_col = "progress_bin_centre" if "progress_bin_centre" in df.columns else "progress_mid"
        sub = df[df["technique"] == tech].sort_values(progress_col)

        ax.plot(sub[progress_col], sub["acceptance_rate"],
                color=colours[0], marker="o", ms=3, lw=1.5, label="Acceptance rate")
        if "improvement_rate" in sub.columns:
            ax.plot(sub[progress_col], sub["improvement_rate"],
                    color=colours[1], marker="s", ms=3, lw=1.5,
                    linestyle="--", label="Improvement rate")

        ax.set_title(tech, fontsize=9, fontweight="bold")
        ax.set_xlabel("Search progress", fontsize=8)
        ax.set_ylabel("Rate", fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=7, loc="best")
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3)

    for idx in range(len(techniques), nrows * ncols):
        row, col = divmod(idx, ncols)
        axes[row][col].set_visible(False)

    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _technique_comparison_section(pdf: PdfPages, models_dir: Path) -> None:
    tc_path = models_dir / "technique_comparison.csv"
    if not tc_path.exists():
        return
    df = pd.read_csv(tc_path)
    _df_to_page(pdf, "Technique Comparison -- Surrogate Faithfulness", df)

    # Also render as a bar chart for visual comparison
    if {"technique", "accuracy", "roc_auc", "majority_baseline"}.issubset(df.columns):
        fig, axes = plt.subplots(1, 2, figsize=(11.69, 6))
        fig.suptitle("Technique Comparison", fontsize=12, fontweight="bold")

        colours = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        techs = df["technique"].tolist()
        x = np.arange(len(techs))
        width = 0.3

        for ax, metric, title in [
            (axes[0], "accuracy",  "Accuracy"),
            (axes[1], "roc_auc",   "ROC-AUC"),
        ]:
            bars = ax.bar(x - width / 2, df[metric], width,
                          label=metric, color=colours[0], alpha=0.85)
            if "majority_baseline" in df.columns and metric == "accuracy":
                ax.bar(x + width / 2, df["majority_baseline"], width,
                       label="majority baseline", color=colours[1], alpha=0.6)
                ax.legend(fontsize=8)
            ax.set_xticks(x)
            ax.set_xticklabels(techs, rotation=20, ha="right", fontsize=8)
            ax.set_ylabel(title, fontsize=9)
            ax.set_title(title, fontsize=10, fontweight="bold")
            ax.set_ylim(0, 1.05)
            ax.grid(axis="y", alpha=0.3)
            for bar in bars:
                h = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.005,
                        f"{h:.3f}", ha="center", va="bottom", fontsize=7)

        fig.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def _ablation_section(pdf: PdfPages, models_dir: Path) -> None:
    tech_dirs = [
        p for p in sorted(models_dir.iterdir())
        if p.is_dir() and not _is_uuid(p.name)
    ]
    for tech_dir in tech_dirs:
        abl_path = tech_dir / "ablation_results.csv"
        if not abl_path.exists():
            continue
        df = pd.read_csv(abl_path)
        _df_to_page(pdf, f"Ablation Results -- {tech_dir.name}", df)

    # Summary bar chart across all techniques
    all_rows = []
    for tech_dir in tech_dirs:
        abl_path = tech_dir / "ablation_results.csv"
        if abl_path.exists():
            df = pd.read_csv(abl_path)
            df["technique"] = tech_dir.name
            all_rows.append(df)
    if not all_rows:
        return

    combined = pd.concat(all_rows, ignore_index=True)
    if "variant" not in combined.columns or "roc_auc" not in combined.columns:
        return

    fig, ax = plt.subplots(figsize=(11.69, 6))
    fig.suptitle("Ablation Study -- ROC-AUC by Variant and Technique",
                 fontsize=12, fontweight="bold")

    variants = combined["variant"].unique()
    techniques = combined["technique"].unique()
    x = np.arange(len(techniques))
    width = 0.25
    colours = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    for i, variant in enumerate(variants):
        vals = [
            combined[(combined["technique"] == t) &
                     (combined["variant"] == variant)]["roc_auc"].values
            for t in techniques
        ]
        vals = [v[0] if len(v) > 0 else np.nan for v in vals]
        offset = (i - len(variants) / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=variant,
               color=colours[i % len(colours)], alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(techniques, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("ROC-AUC", fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _shap_heatmap_section(pdf: PdfPages, explanations_dir: Path) -> None:
    csv_path = explanations_dir / "shap_comparison_by_technique.csv"
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path)
    if df.empty:
        return

    pivot = df.pivot_table(
        index="feature", columns="technique", values="mean_abs_shap", aggfunc="mean"
    )
    if pivot.empty:
        return

    # Table view
    flat = pivot.reset_index().round(4)
    _df_to_page(pdf, "SHAP Cross-Technique Comparison (Table)", flat)

    # Heatmap
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    data        = pivot.values.astype(float)
    data_filled = np.where(np.isnan(data), 0.0, data)

    im = ax.imshow(data_filled, aspect="auto", cmap="YlOrRd", interpolation="nearest")
    plt.colorbar(im, ax=ax, label="Mean |SHAP value|", shrink=0.75)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)

    vmax = data_filled.max()
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val    = pivot.values[i, j]
            text   = f"{val:.3f}" if not np.isnan(val) else "N/A"
            colour = "white" if data_filled[i, j] > vmax * 0.6 else "black"
            ax.text(j, i, text, ha="center", va="center", fontsize=7, color=colour)

    ax.set_title("Cross-Technique SHAP Feature Importance Heatmap",
                 fontsize=12, fontweight="bold", pad=15)
    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def _shap_bar_charts_section(pdf: PdfPages, explanations_dir: Path) -> None:
    tech_dirs = [
        p for p in sorted(explanations_dir.iterdir())
        if p.is_dir() and not _is_uuid(p.name)
    ]
    if not tech_dirs:
        return

    colours = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    for tech_dir in tech_dirs:
        csv_path = tech_dir / "shap_global_importance.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        if df.empty or len(df.columns) < 2:
            continue

        feat_col  = df.columns[0]
        value_col = df.columns[1]
        df = df.nlargest(15, value_col).sort_values(value_col, ascending=True)

        fig, ax = plt.subplots(figsize=(11.69, 7))
        bars = ax.barh(df[feat_col], df[value_col],
                       color=colours[0], alpha=0.82, edgecolor="white")
        for bar in bars:
            w = bar.get_width()
            ax.text(w + df[value_col].max() * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{w:.4f}", va="center", ha="left", fontsize=8)

        ax.set_title(f"SHAP Global Feature Importance -- {tech_dir.name}",
                     fontsize=12, fontweight="bold")
        ax.set_xlabel("Mean |SHAP value|", fontsize=10)
        ax.tick_params(axis="y", labelsize=9)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="x", alpha=0.3)
        fig.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def _lime_section(pdf: PdfPages, explanations_dir: Path) -> None:
    tech_dirs = [
        p for p in sorted(explanations_dir.iterdir())
        if p.is_dir() and not _is_uuid(p.name)
    ]
    for tech_dir in tech_dirs:
        lime_path = tech_dir / "lime_condition_frequency.csv"
        if not lime_path.exists():
            continue
        df   = pd.read_csv(lime_path)
        top  = df.nlargest(20, "count")
        _df_to_page(pdf, f"LIME Condition Frequency -- {tech_dir.name}", top)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_report(
    interim_dir: Path,
    processed_dir: Path,
    models_dir: Path,
    explanations_dir: Path,
    out_path: Path,
) -> None:
    """Generate a multi-page PDF report of all xai-sphh pipeline outputs.

    :param interim_dir:      data/interim  (run_metadata.parquet)
    :param processed_dir:    data/processed (contains yates/ subdirectory)
    :param models_dir:       results/models
    :param explanations_dir: results/explanations
    :param out_path:         destination PDF file path
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    yates_dir = processed_dir / "yates"

    run_meta: pd.DataFrame | None = None
    meta_path = interim_dir / "run_metadata.parquet"
    if meta_path.exists():
        run_meta = pd.read_parquet(meta_path)

    with PdfPages(str(out_path)) as pdf:

        _cover_page(pdf, run_meta)

        _section_header(pdf, "Section 1", "Run Metadata",
                        "Technique, domain, instance, seed and stub flag per run")
        _run_metadata_section(pdf, interim_dir)

        _section_header(pdf, "Section 2", "Log-Return Statistics",
                        "Per-heuristic count, mean, median, IQR, trimmed mean, std")
        _log_returns_section(pdf, yates_dir)

        _section_header(pdf, "Section 3", "Acceptance Rate vs Search Progress",
                        "Acceptance and improvement rate binned over feat_progress")
        _acceptance_rate_section(pdf, yates_dir)

        _section_header(pdf, "Section 4", "Technique Comparison",
                        "Surrogate accuracy, ROC-AUC and majority baseline per technique")
        _technique_comparison_section(pdf, models_dir)

        _section_header(pdf, "Section 5", "Ablation Study",
                        "Effect of removing identity (feat_last_h*) or class (feat_last_class*) features")
        _ablation_section(pdf, models_dir)

        _section_header(pdf, "Section 6", "SHAP Cross-Technique Comparison",
                        "Mean absolute SHAP value per feature across all techniques")
        _shap_heatmap_section(pdf, explanations_dir)

        _section_header(pdf, "Section 7", "Per-Technique SHAP Importance",
                        "Top-15 features by mean |SHAP| value for each technique")
        _shap_bar_charts_section(pdf, explanations_dir)

        _section_header(pdf, "Section 8", "LIME Condition Frequency",
                        "Most frequent local explanation conditions per technique (top 20)")
        _lime_section(pdf, explanations_dir)

        info = pdf.infodict()
        info["Title"]   = "xai-sphh Pipeline Results Report"
        info["Subject"] = "Explainable AI for Selection Perturbative Hyper-Heuristics"
        info["Creator"] = "xaisphh report command"
