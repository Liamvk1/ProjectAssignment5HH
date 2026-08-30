#!/usr/bin/env bash
# run_experiments.sh
#
# Runs the Java experiment runner for all YAML files found under config/experiments/.
# Traces are written to the outputDirectory specified in each config file.
#
# Usage:
#   ./scripts/run_experiments.sh
#   ./scripts/run_experiments.sh config/experiments/baseline.yaml

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JAR="${REPO_ROOT}/build/libs/xai-sphh-0.1.0-SNAPSHOT.jar"

if [[ ! -f "${JAR}" ]]; then
    echo "ERROR: Jar not found at ${JAR}. Run './gradlew build' first." >&2
    exit 1
fi

if [[ $# -gt 0 ]]; then
    CONFIGS=("$@")
else
    mapfile -t CONFIGS < <(find "${REPO_ROOT}/config/experiments" -name "*.yaml" | sort)
fi

if [[ ${#CONFIGS[@]} -eq 0 ]]; then
    echo "No experiment config files found." >&2
    exit 1
fi

for config in "${CONFIGS[@]}"; do
    echo "Running experiment: ${config}"
    java -jar "${JAR}" "${config}"
done

echo "All experiments complete."
