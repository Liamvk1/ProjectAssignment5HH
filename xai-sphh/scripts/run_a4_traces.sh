#!/usr/bin/env bash
# Generate all 24 Assessment 4 traces (non-PS at 100k, PS at 10k).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

CONFIGS_DIR="data/tmp_configs"
LOG="data/raw/traces/run_log.txt"
> "${LOG}"

TOTAL=0
FAILED=0

run_one() {
    local config="$1"
    local stem
    stem=$(basename "${config}" .yaml)
    echo "--- [$(date +%H:%M:%S)] Running ${stem} ---"
    local start_s
    start_s=$(date +%s)
    if ./gradlew run -q --args="${config}" 2>&1; then
        local end_s
        end_s=$(date +%s)
        local elapsed=$(( end_s - start_s ))
        echo "  OK in ${elapsed}s" | tee -a "${LOG}"
        echo "${stem},${elapsed},OK" >> "${LOG}"
    else
        echo "  FAILED" | tee -a "${LOG}"
        echo "${stem},0,FAILED" >> "${LOG}"
        FAILED=$((FAILED + 1))
    fi
    TOTAL=$((TOTAL + 1))
}

# Non-PS domains first (fast)
for domain in SAT BinPacking FlowShop TSP VRP; do
    for config in "${CONFIGS_DIR}"/*_${domain}_0_42.yaml; do
        run_one "${config}"
    done
done

# PersonnelScheduling last (slow, 10k iterations)
for config in "${CONFIGS_DIR}"/*_PersonnelScheduling_0_42.yaml; do
    run_one "${config}"
done

echo ""
echo "=== Complete: ${TOTAL} runs, ${FAILED} failures ==="
echo "Trace files:"
ls -lh data/raw/traces/trace_*.csv 2>/dev/null | awk '{print "  "$NF, $5}'
