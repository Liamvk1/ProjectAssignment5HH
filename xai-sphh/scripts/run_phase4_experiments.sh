#!/usr/bin/env bash
# Phase 4: Run all XAI variant experiments on held-out instance 1.
#
# Matrix: 2 base techniques x 5 variants x 6 domains x 10 seeds = 600 runs.
#
# Usage:
#   bash scripts/run_phase4_experiments.sh [--dry-run]
#
# Resumable: skips runs whose trace files already exist.
# Requires: rules/ directory with 48 JSON rule files from Phase 2.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY RUN] Would generate configs but not execute."
fi

# Per-domain iteration budgets (same as A5).
declare -A BUDGETS
BUDGETS[SAT]=50000
BUDGETS[BinPacking]=100000
BUDGETS[FlowShop]=100000
BUDGETS[TSP]=10000
BUDGETS[VRP]=50000
BUDGETS[PersonnelScheduling]=5000

DOMAINS=(SAT BinPacking FlowShop TSP VRP PersonnelScheduling)
SEEDS=(11 22 33 44 55 66 77 88 99 111)

# Base techniques and their XAI variants.
# Each base technique has 5 variants: base, -XAI, -XAI-LODO, -RAND, -STAT.
BASE_TECHNIQUES=(SP-CF-AILTA MP-CF)
MASK_SUFFIXES=("" "-XAI" "-XAI-LODO" "-RAND" "-STAT")

INSTANCE=1
OUTPUT_DIR="results/rq2/traces"
CONFIG_DIR="config/phase4"
RULES_DIR="rules"

mkdir -p "$OUTPUT_DIR" "$CONFIG_DIR"

TOTAL=0
SKIPPED=0
COMPLETED=0
FAILED=0

for BASE in "${BASE_TECHNIQUES[@]}"; do
    for SUFFIX in "${MASK_SUFFIXES[@]}"; do
        TECHNIQUE="${BASE}${SUFFIX}"
        for DOMAIN in "${DOMAINS[@]}"; do
            for SEED in "${SEEDS[@]}"; do
                TOTAL=$((TOTAL + 1))
                STEM="${TECHNIQUE}_${DOMAIN}_${INSTANCE}_${SEED}"
                TRACE_FILE="${OUTPUT_DIR}/trace_${STEM}.csv"

                # Skip if already done.
                if [[ -f "$TRACE_FILE" ]]; then
                    SKIPPED=$((SKIPPED + 1))
                    continue
                fi

                BUDGET=${BUDGETS[$DOMAIN]}

                # For MP-CF variants, scale budget per population member.
                BUDGET_SCALING="none"
                if [[ "$BASE" == "MP-CF" ]]; then
                    BUDGET_SCALING="per_member"
                fi

                # Build technique parameters.
                TECHNIQUE_PARAMS=""
                if [[ -n "$SUFFIX" ]]; then
                    TECHNIQUE_PARAMS="    rulesDir: \"${RULES_DIR}\""
                fi

                # AILTA needs totalIterations estimate.
                if [[ "$BASE" == "SP-CF-AILTA" ]]; then
                    if [[ -n "$TECHNIQUE_PARAMS" ]]; then
                        TECHNIQUE_PARAMS="${TECHNIQUE_PARAMS}
    totalIterations: \"${BUDGET}\""
                    else
                        TECHNIQUE_PARAMS="    totalIterations: \"${BUDGET}\""
                    fi
                fi

                # Write YAML config.
                CONFIG_FILE="${CONFIG_DIR}/${STEM}.yaml"
                cat > "$CONFIG_FILE" <<YAML
techniqueName: "${TECHNIQUE}"
domain: "${DOMAIN}"
instanceIndex: ${INSTANCE}
seed: ${SEED}
budgetType: "iterations"
budgetValue: ${BUDGET}
budgetScaling: "${BUDGET_SCALING}"
outputDirectory: "${OUTPUT_DIR}"
techniqueParameters:
$(if [[ -n "$TECHNIQUE_PARAMS" ]]; then echo "$TECHNIQUE_PARAMS"; else echo "    {}"; fi)
YAML

                if $DRY_RUN; then
                    echo "[DRY RUN] Would run: $STEM"
                    continue
                fi

                echo "[$(date +%H:%M:%S)] Running ${STEM} (budget=${BUDGET})..."
                if ./gradlew run --args="$CONFIG_FILE" < /dev/null > /dev/null 2>&1; then
                    COMPLETED=$((COMPLETED + 1))
                    echo "  -> OK ($COMPLETED completed, $SKIPPED skipped, $FAILED failed / $TOTAL total)"
                else
                    FAILED=$((FAILED + 1))
                    echo "  -> FAILED ($STEM)"
                fi
            done
        done
    done
done

echo ""
echo "=== Phase 4 experiment run complete ==="
echo "Total: $TOTAL, Completed: $COMPLETED, Skipped: $SKIPPED, Failed: $FAILED"
