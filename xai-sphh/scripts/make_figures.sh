#!/usr/bin/env bash
# make_figures.sh
#
# Runs the full Python analysis pipeline and produces all report figures.
#
# Usage:
#   ./scripts/make_figures.sh [processed_dir] [results_dir] [figures_dir]

set -euo pipefail

PROCESSED="${1:-data/processed}"
RESULTS="${2:-results}"
FIGURES="${3:-report/figures}"

echo "Step 1: Computing Yates reference measures..."
python -m xaisphh.cli yates --processed "${PROCESSED}" --out "${RESULTS}/tables"

echo "Step 2: Training surrogate model..."
python -m xaisphh.cli train --processed "${PROCESSED}" --out "${RESULTS}"

echo "Step 3: Generating explanations..."
python -m xaisphh.cli explain --results "${RESULTS}" --out "${RESULTS}/figures"

echo "Step 4: Rendering report figures..."
python -m xaisphh.cli figures --results "${RESULTS}" --out "${FIGURES}"

echo "Figures written to ${FIGURES}."
