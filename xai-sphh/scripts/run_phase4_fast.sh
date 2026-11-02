#!/usr/bin/env bash
# Phase 4: Fast parallel experiment runner.
#
# Runs all 600 experiments using direct java (no Gradle overhead per run),
# split across N parallel JVM workers. Each worker gets a batch of configs
# and runs them sequentially within a single JVM.
#
# Usage:
#   bash scripts/run_phase4_fast.sh [NUM_WORKERS]  (default: 6)
#
# Resumable: skips runs whose trace files already exist.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

NUM_WORKERS=${1:-6}

# Ensure installDist is up to date.
echo "[$(date +%H:%M:%S)] Building project..."
./gradlew installDist -q 2>&1

# Build classpath from installed distribution.
CP=$(echo build/install/xai-sphh/lib/*.jar | tr ' ' ':')

# Per-domain iteration budgets.
declare -A BUDGETS
BUDGETS[SAT]=50000
BUDGETS[BinPacking]=100000
BUDGETS[FlowShop]=100000
BUDGETS[TSP]=10000
BUDGETS[VRP]=50000
BUDGETS[PersonnelScheduling]=5000

DOMAINS=(SAT BinPacking FlowShop TSP VRP PersonnelScheduling)
SEEDS=(11 22 33 44 55 66 77 88 99 111)
BASE_TECHNIQUES=(SP-CF-AILTA MP-CF)
MASK_SUFFIXES=("" "-XAI" "-XAI-LODO" "-RAND" "-STAT")

INSTANCE=1
OUTPUT_DIR="results/rq2/traces"
CONFIG_DIR="config/phase4"
RULES_DIR="rules"

mkdir -p "$OUTPUT_DIR" "$CONFIG_DIR"

# Generate all configs, collecting only those that need running.
PENDING_CONFIGS=()

for BASE in "${BASE_TECHNIQUES[@]}"; do
    for SUFFIX in "${MASK_SUFFIXES[@]}"; do
        TECHNIQUE="${BASE}${SUFFIX}"
        for DOMAIN in "${DOMAINS[@]}"; do
            for SEED in "${SEEDS[@]}"; do
                STEM="${TECHNIQUE}_${DOMAIN}_${INSTANCE}_${SEED}"
                TRACE_FILE="${OUTPUT_DIR}/trace_${STEM}.csv"

                # Skip already completed.
                if [[ -f "$TRACE_FILE" ]]; then
                    continue
                fi

                BUDGET=${BUDGETS[$DOMAIN]}
                BUDGET_SCALING="none"
                if [[ "$BASE" == "MP-CF" ]]; then
                    BUDGET_SCALING="per_member"
                fi

                TECHNIQUE_PARAMS=""
                if [[ -n "$SUFFIX" ]]; then
                    TECHNIQUE_PARAMS="    rulesDir: \"${RULES_DIR}\""
                fi
                if [[ "$BASE" == "SP-CF-AILTA" ]]; then
                    if [[ -n "$TECHNIQUE_PARAMS" ]]; then
                        TECHNIQUE_PARAMS="${TECHNIQUE_PARAMS}
    totalIterations: \"${BUDGET}\""
                    else
                        TECHNIQUE_PARAMS="    totalIterations: \"${BUDGET}\""
                    fi
                fi

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

                PENDING_CONFIGS+=("$CONFIG_FILE")
            done
        done
    done
done

TOTAL=${#PENDING_CONFIGS[@]}
echo "[$(date +%H:%M:%S)] ${TOTAL} experiments pending (already completed: $((600 - TOTAL)))"

if [[ $TOTAL -eq 0 ]]; then
    echo "Nothing to do."
    exit 0
fi

# Split configs into N worker batches (round-robin).
BATCH_DIR=$(mktemp -d)
for ((w=0; w<NUM_WORKERS; w++)); do
    : > "$BATCH_DIR/worker_${w}.txt"
done

for ((i=0; i<TOTAL; i++)); do
    w=$((i % NUM_WORKERS))
    echo "${PENDING_CONFIGS[$i]}" >> "$BATCH_DIR/worker_${w}.txt"
done

echo "[$(date +%H:%M:%S)] Launching ${NUM_WORKERS} parallel workers..."

# Launch workers.
PIDS=()
for ((w=0; w<NUM_WORKERS; w++)); do
    BATCH_FILE="$BATCH_DIR/worker_${w}.txt"
    COUNT=$(wc -l < "$BATCH_FILE")
    if [[ $COUNT -eq 0 ]]; then
        continue
    fi

    CONFIGS=$(tr '\n' ' ' < "$BATCH_FILE")
    echo "  Worker $w: $COUNT configs"

    java -cp "$CP" za.ac.up.cos790.Main $CONFIGS \
        > "$BATCH_DIR/worker_${w}.log" 2>&1 &
    PIDS+=($!)
done

echo "[$(date +%H:%M:%S)] All workers launched. Waiting..."

# Wait and report.
FAIL=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "=== Phase 4 complete ==="
echo "[$(date +%H:%M:%S)] Workers finished. Failed workers: $FAIL"
echo "Traces produced: $(ls "$OUTPUT_DIR"/trace_*.csv 2>/dev/null | wc -l) / 600"

# Show any errors from worker logs.
for log in "$BATCH_DIR"/worker_*.log; do
    if grep -q "FAILED" "$log" 2>/dev/null; then
        echo ""
        echo "--- Errors from $(basename "$log") ---"
        grep "FAILED" "$log"
    fi
done

rm -rf "$BATCH_DIR"
