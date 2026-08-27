#!/usr/bin/env bash
# extract_heuristic_catalogue.sh
#
# Prints the heuristic catalogue for each registered domain by invoking a
# lightweight Java utility that queries each HyFlex domain object.
#
# This script is a documentation aid. Run it after placing HyFlex jars in
# lib/hyflex/ to verify that the catalogue is being read correctly.
#
# Usage:
#   ./scripts/extract_heuristic_catalogue.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JAR="${REPO_ROOT}/build/libs/xai-sphh-0.1.0-SNAPSHOT.jar"

if [[ ! -f "${JAR}" ]]; then
    echo "ERROR: Jar not found at ${JAR}. Run './gradlew build' first." >&2
    exit 1
fi

# TODO: Add a --catalogue-only flag to Main.java or a separate entry point
#       that prints the catalogue for each domain and exits.
echo "TODO: implement catalogue extraction entry point in Java."
echo "The HeuristicCatalogue class in za.ac.up.cos790.domain reads the catalogue"
echo "from the HyFlex domain object at runtime. See HeuristicCatalogue.java."
