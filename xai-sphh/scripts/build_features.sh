#!/usr/bin/env bash
# build_features.sh
#
# Runs the Python feature matrix assembly step over all trace files.
#
# Usage:
#   ./scripts/build_features.sh [traces_dir] [interim_dir] [processed_dir]

set -euo pipefail

TRACES="${1:-data/raw/traces}"
INTERIM="${2:-data/interim}"
PROCESSED="${3:-data/processed}"

echo "Step 1: Loading traces from ${TRACES}..."
python -m xaisphh.cli load --traces "${TRACES}" --out "${INTERIM}"

echo "Step 2: Building feature matrix from ${INTERIM}..."
python -m xaisphh.cli features --interim "${INTERIM}" --out "${PROCESSED}"

echo "Feature matrix written to ${PROCESSED}."
