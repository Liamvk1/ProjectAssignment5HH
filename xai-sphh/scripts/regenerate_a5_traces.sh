#!/usr/bin/env bash
# Regenerate all 240 Assessment 5 trace files.
# Usage: bash scripts/regenerate_a5_traces.sh
# Resumable: skips runs whose trace file already exists.
# Estimated wall time: ~20 hours (dominated by PersonnelScheduling).

set -euo pipefail
cd "$(dirname "$0")/.."

TRACES_DIR="results/a5/traces"
CONFIGS_DIR="config/generated"
mkdir -p "$TRACES_DIR" "$CONFIGS_DIR"

TECHNIQUES=("SP-SR-LA" "SP-CF-LA" "SP-CF-AILTA" "MP-CF")
DOMAINS=("SAT" "BinPacking" "FlowShop" "TSP" "VRP" "PersonnelScheduling")
SEEDS=(42 123 456 789 1024 2048 3141 4242 5555 9999)

# Per-domain budgets from A5 convergence analysis
declare -A BUDGETS
BUDGETS[SAT]=50000
BUDGETS[BinPacking]=100000
BUDGETS[FlowShop]=100000
BUDGETS[TSP]=10000
BUDGETS[VRP]=50000
BUDGETS[PersonnelScheduling]=5000

TOTAL=240
DONE=0
SKIPPED=0
FAILED=0

echo "=== Regenerating A5 traces (${TOTAL} runs) ==="
echo "Output directory: ${TRACES_DIR}"
echo ""

for technique in "${TECHNIQUES[@]}"; do
  for domain in "${DOMAINS[@]}"; do
    budget=${BUDGETS[$domain]}
    for seed in "${SEEDS[@]}"; do
      stem="${technique}_${domain}_0_${seed}"
      trace_file="${TRACES_DIR}/trace_${stem}.csv"

      # Skip if already done
      if [[ -f "$trace_file" ]]; then
        SKIPPED=$((SKIPPED + 1))
        DONE=$((DONE + 1))
        continue
      fi

      # Build technique parameters block
      tech_params=""
      case "$technique" in
        SP-CF-LA|SP-SR-LA)
          tech_params="  listLength: 50"
          ;;
        SP-CF-AILTA)
          tech_params="  totalIterations: ${budget}"
          ;;
        MP-CF)
          tech_params="  populationSize: 10"
          ;;
      esac

      # Write temp config
      config_file="${CONFIGS_DIR}/${stem}.yaml"
      cat > "$config_file" <<EOF
techniqueName: ${technique}
domain: ${domain}
instanceIndex: 0
seed: ${seed}
budgetType: iterations
budgetValue: ${budget}
outputDirectory: ${TRACES_DIR}
techniqueParameters:
${tech_params}
EOF

      progress=$((DONE + 1))
      echo "[${progress}/${TOTAL}] ${technique} | ${domain} | seed=${seed} | budget=${budget}"

      if ./gradlew run --args="$config_file" --quiet 2>&1; then
        DONE=$((DONE + 1))
        echo "  -> OK"
      else
        FAILED=$((FAILED + 1))
        DONE=$((DONE + 1))
        echo "  -> FAILED"
      fi
    done
  done
done

echo ""
echo "=== Summary ==="
echo "Completed: $((DONE - SKIPPED - FAILED))"
echo "Skipped (already existed): ${SKIPPED}"
echo "Failed: ${FAILED}"
echo "Total: ${DONE}/${TOTAL}"

# Count actual trace files
actual=$(ls -1 "${TRACES_DIR}"/trace_*.csv 2>/dev/null | wc -l)
echo "Trace files in ${TRACES_DIR}: ${actual}"
