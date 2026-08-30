"""
Shared matplotlib style for all report figures.

Import and call :func:`apply_style` at the start of any module that produces a
figure, to ensure consistent appearance across all plots in the report.
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt


def apply_style() -> None:
    """Apply the project-wide matplotlib style to the current session.

    Sets font sizes, line widths, figure dimensions, and colour cycle so that
    every figure in the report is visually consistent. Call once per script or
    notebook before creating any figures.
    """
    mpl.rcParams.update({
        # Typography
        "font.family":        "serif",
        "font.size":          10,
        "axes.titlesize":     11,
        "axes.labelsize":     10,
        "xtick.labelsize":    9,
        "ytick.labelsize":    9,
        "legend.fontsize":    9,
        # Figure dimensions (width in inches for a single-column LaTeX figure)
        "figure.figsize":     (5.0, 3.5),
        "figure.dpi":         150,
        # Lines
        "lines.linewidth":    1.5,
        "axes.linewidth":     0.8,
        # Grid
        "axes.grid":          True,
        "grid.alpha":         0.3,
        "grid.linestyle":     "--",
        # Output format
        "savefig.dpi":        300,
        "savefig.bbox":       "tight",
        "savefig.format":     "pdf",
    })


#: Colour cycle aligned with a colour-blind-friendly palette.
COLOURS: list[str] = [
    "#0072B2",  # blue
    "#E69F00",  # orange
    "#009E73",  # green
    "#CC79A7",  # pink
    "#56B4E9",  # light blue
    "#D55E00",  # vermilion
    "#F0E442",  # yellow
]


def domain_colour(domain_name: str) -> str:
    """Return a consistent colour for a given domain name.

    :param domain_name: HyFlex domain name (e.g. ``"SAT"``, ``"TSP"``)
    :return: hex colour string
    """
    domains = ["SAT", "BinPacking", "PersonnelScheduling", "FlowShop", "TSP", "VRP"]
    idx = domains.index(domain_name) if domain_name in domains else 0
    return COLOURS[idx % len(COLOURS)]
