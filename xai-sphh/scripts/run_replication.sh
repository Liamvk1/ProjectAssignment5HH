#!/usr/bin/env bash
# ===========================================================================
#  Replication runner for XAI-SPHH experiments
#
#  Usage:
#    ./scripts/run_replication.sh                     # interactive menu
#    ./scripts/run_replication.sh full                # all 10 seeds, all domains, all techniques
#    ./scripts/run_replication.sh pilot               # 2 seeds only
#    ./scripts/run_replication.sh --seeds 42,123 --domains SAT,TSP --techniques SP-CF-LA,MP-CF
#    ./scripts/run_replication.sh --dry-run full      # show what would run without running
#
#  Flags:
#    --seeds <list>        Comma-separated seeds       (default: all from config/seeds.txt)
#    --domains <list>      Comma-separated domains     (default: all 6)
#    --techniques <list>   Comma-separated techniques  (default: all 4)
#    --dry-run             Print the run matrix and exit
#    --force               Re-run even if trace exists (overwrites)
# ===========================================================================
set -eu
cd "$(dirname "$0")/.."

# ---- Defaults ------------------------------------------------------------
SEEDS_FILE="config/seeds.txt"
OUT_DIR="results/a5/traces"
CONFIG_DIR="results/a5/configs"
LOG_FILE="results/a5/run_log.csv"

ALL_DOMAINS="SAT BinPacking FlowShop TSP VRP PersonnelScheduling"
ALL_TECHNIQUES="SP-CF-LA SP-CF-AILTA SP-SR-LA MP-CF"

# Per-domain budgets (from convergence analysis)
budget_for() {
    case "$1" in
        SAT)                   echo 50000  ;;
        BinPacking)            echo 100000 ;;
        FlowShop)              echo 100000 ;;
        TSP)                   echo 10000  ;;
        VRP)                   echo 50000  ;;
        PersonnelScheduling)   echo 5000   ;;
        *) echo "ERROR: unknown domain '$1'" >&2; exit 1 ;;
    esac
}

# ---- Parse arguments ------------------------------------------------------
ARG_SEEDS=""
ARG_DOMAINS=""
ARG_TECHNIQUES=""
DRY_RUN=false
FORCE=false
MODE=""

while [ $# -gt 0 ]; do
    case "$1" in
        full)          MODE="full";    shift ;;
        pilot)         MODE="pilot";   shift ;;
        --seeds)       ARG_SEEDS="$2"; shift 2 ;;
        --domains)     ARG_DOMAINS="$2"; shift 2 ;;
        --techniques)  ARG_TECHNIQUES="$2"; shift 2 ;;
        --dry-run)     DRY_RUN=true;   shift ;;
        --force)       FORCE=true;     shift ;;
        -h|--help)
            head -20 "$0" | grep '^#' | sed 's/^# \?//'
            exit 0 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ---- Interactive menu if no mode or filters given --------------------------
if [ -z "$MODE" ] && [ -z "$ARG_SEEDS" ] && [ -z "$ARG_DOMAINS" ] && [ -z "$ARG_TECHNIQUES" ]; then
    echo "============================================"
    echo "  XAI-SPHH Experiment Runner"
    echo "============================================"
    echo ""
    echo "  1) full        All 10 seeds x 6 domains x 4 techniques (240 runs)"
    echo "  2) pilot       2 seeds x 6 domains x 4 techniques (48 runs)"
    echo "  3) single      Pick one domain, one technique, one seed"
    echo "  4) domain      All techniques + seeds for one domain"
    echo "  5) technique   All domains + seeds for one technique"
    echo "  6) custom      Enter seeds, domains, techniques manually"
    echo "  7) status      Show progress (existing traces vs total)"
    echo ""
    printf "  Select [1-7]: "
    read -r CHOICE

    case "$CHOICE" in
        1) MODE="full" ;;
        2) MODE="pilot" ;;
        3)
            echo ""
            echo "  Domains: $ALL_DOMAINS"
            printf "  Domain: "; read -r ARG_DOMAINS
            echo "  Techniques: $ALL_TECHNIQUES"
            printf "  Technique: "; read -r ARG_TECHNIQUES
            printf "  Seed: "; read -r ARG_SEEDS
            ;;
        4)
            echo ""
            echo "  Domains: $ALL_DOMAINS"
            printf "  Domain: "; read -r ARG_DOMAINS
            ;;
        5)
            echo ""
            echo "  Techniques: $ALL_TECHNIQUES"
            printf "  Technique: "; read -r ARG_TECHNIQUES
            ;;
        6)
            echo ""
            printf "  Seeds (comma-separated, or 'all'): "; read -r ARG_SEEDS
            printf "  Domains (comma-separated, or 'all'): "; read -r ARG_DOMAINS
            printf "  Techniques (comma-separated, or 'all'): "; read -r ARG_TECHNIQUES
            ;;
        7)
            # Status report
            echo ""
            TOTAL_EXPECTED=240
            EXISTING=$(find "$OUT_DIR" -name "trace_*.csv" 2>/dev/null | wc -l)
            echo "  Traces: $EXISTING / $TOTAL_EXPECTED"
            echo ""
            for d in $ALL_DOMAINS; do
                COUNT=$(find "$OUT_DIR" -name "trace_*_${d}_0_*.csv" 2>/dev/null | wc -l)
                EXPECTED=40  # 4 techniques x 10 seeds
                printf "  %-25s %2d / %2d" "$d" "$COUNT" "$EXPECTED"
                if [ "$COUNT" -eq "$EXPECTED" ]; then
                    echo "  DONE"
                else
                    echo "  ($(( EXPECTED - COUNT )) remaining)"
                fi
            done
            exit 0
            ;;
        *) echo "Invalid choice."; exit 1 ;;
    esac
fi

# ---- Resolve seeds ---------------------------------------------------------
mapfile -t FILE_SEEDS < "$SEEDS_FILE"

if [ -n "$ARG_SEEDS" ] && [ "$ARG_SEEDS" != "all" ]; then
    IFS=',' read -ra SEEDS <<< "$ARG_SEEDS"
elif [ "$MODE" = "pilot" ]; then
    SEEDS=("${FILE_SEEDS[@]:0:2}")
else
    SEEDS=("${FILE_SEEDS[@]}")
fi

# ---- Resolve domains -------------------------------------------------------
if [ -n "$ARG_DOMAINS" ] && [ "$ARG_DOMAINS" != "all" ]; then
    IFS=',' read -ra DOMAINS <<< "$ARG_DOMAINS"
else
    IFS=' ' read -ra DOMAINS <<< "$ALL_DOMAINS"
fi

# ---- Resolve techniques ----------------------------------------------------
if [ -n "$ARG_TECHNIQUES" ] && [ "$ARG_TECHNIQUES" != "all" ]; then
    IFS=',' read -ra TECHNIQUES <<< "$ARG_TECHNIQUES"
else
    IFS=' ' read -ra TECHNIQUES <<< "$ALL_TECHNIQUES"
fi

# ---- Print run matrix ------------------------------------------------------
TOTAL_RUNS=$(( ${#SEEDS[@]} * ${#DOMAINS[@]} * ${#TECHNIQUES[@]} ))

echo ""
echo "=== Run Matrix ==="
echo "  Seeds:      ${SEEDS[*]}"
echo "  Domains:    ${DOMAINS[*]}"
echo "  Techniques: ${TECHNIQUES[*]}"
echo "  Total runs: $TOTAL_RUNS"
echo ""
echo "  Per-domain budgets:"
for d in "${DOMAINS[@]}"; do
    b=$(budget_for "$d")
    printf "    %-25s %'7d iterations\n" "$d" "$b"
done
echo ""

if $DRY_RUN; then
    echo "  [DRY RUN] Would execute $TOTAL_RUNS runs. Listing:"
    for seed in "${SEEDS[@]}"; do
        for domain in "${DOMAINS[@]}"; do
            b=$(budget_for "$domain")
            for technique in "${TECHNIQUES[@]}"; do
                stem="${technique}_${domain}_0_${seed}"
                trace="$OUT_DIR/trace_${stem}.csv"
                if [ -f "$trace" ] && ! $FORCE; then
                    echo "    SKIP $stem (exists)"
                else
                    echo "    RUN  $stem  budget=$b"
                fi
            done
        done
    done
    exit 0
fi

# ---- Run experiments -------------------------------------------------------
mkdir -p "$OUT_DIR" "$CONFIG_DIR"

# Append to log (don't overwrite on resume)
if [ ! -f "$LOG_FILE" ]; then
    echo "technique,domain,seed,budget,elapsed_s,status" > "$LOG_FILE"
fi

COMPLETED=0
FAILED=0
SKIPPED=0
TOTAL_ELAPSED=0
RUN_COUNT=0

for seed in "${SEEDS[@]}"; do
    for domain in "${DOMAINS[@]}"; do
        budget=$(budget_for "$domain")
        for technique in "${TECHNIQUES[@]}"; do
            RUN_COUNT=$((RUN_COUNT + 1))
            STEM="${technique}_${domain}_0_${seed}"
            TRACE="$OUT_DIR/trace_${STEM}.csv"

            # Skip if trace already exists
            if [ -f "$TRACE" ] && ! $FORCE; then
                echo "[$RUN_COUNT/$TOTAL_RUNS] SKIP $STEM (exists)"
                SKIPPED=$((SKIPPED + 1))
                continue
            fi

            # Generate config
            CONFIG="$CONFIG_DIR/${STEM}.yaml"
            TECH_PARAMS=""
            case "$technique" in
                SP-CF-LA|SP-SR-LA) TECH_PARAMS="  listLength: 50" ;;
                SP-CF-AILTA)       TECH_PARAMS="  totalIterations: $budget" ;;
                MP-CF)             TECH_PARAMS="  populationSize: 10" ;;
            esac

            cat > "$CONFIG" <<YAML
techniqueName: $technique
domain: $domain
instanceIndex: 0
seed: $seed
budgetType: iterations
budgetValue: $budget
outputDirectory: $OUT_DIR
techniqueParameters:
$TECH_PARAMS
YAML

            printf "[%d/%d] [%s] %s (budget=%d) ... " \
                "$RUN_COUNT" "$TOTAL_RUNS" "$(date +%H:%M:%S)" "$STEM" "$budget"

            START_S=$(date +%s)
            if ./gradlew run -q --args="$CONFIG" 2>&1; then
                END_S=$(date +%s)
                ELAPSED=$((END_S - START_S))
                TOTAL_ELAPSED=$((TOTAL_ELAPSED + ELAPSED))
                echo "OK ${ELAPSED}s"
                echo "$technique,$domain,$seed,$budget,$ELAPSED,OK" >> "$LOG_FILE"
                COMPLETED=$((COMPLETED + 1))
            else
                echo "FAILED"
                echo "$technique,$domain,$seed,$budget,0,FAILED" >> "$LOG_FILE"
                FAILED=$((FAILED + 1))
            fi
        done
    done
done

# ---- Summary ---------------------------------------------------------------
echo ""
echo "============================================"
echo "  Summary"
echo "============================================"
echo "  Completed: $COMPLETED"
echo "  Skipped:   $SKIPPED (already existed)"
echo "  Failed:    $FAILED"
echo "  Wall time: ${TOTAL_ELAPSED}s ($((TOTAL_ELAPSED / 3600))h $((TOTAL_ELAPSED % 3600 / 60))m)"
echo ""
EXISTING=$(find "$OUT_DIR" -name "trace_*.csv" 2>/dev/null | wc -l)
echo "  Total traces on disk: $EXISTING / 240"
echo "  Log: $LOG_FILE"
echo "============================================"
