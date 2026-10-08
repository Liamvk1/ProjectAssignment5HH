#!/usr/bin/env bash
# run_domain.sh
#
# Interactive experiment runner. Choose a domain (or all), a technique (or all),
# and optionally override instance index, seed, and budget. Results are written
# to data/raw/traces/ and a metrics summary is printed after each run.
#
# Usage (interactive menu -- no arguments):
#   bash scripts/run_domain.sh
#
# Usage (non-interactive):
#   bash scripts/run_domain.sh [OPTIONS]
#
# Options:
#   --domain     SAT|BinPacking|FlowShop|TSP|VRP|PersonnelScheduling|all
#                (default: interactive menu)
#   --technique  SP-CF-LA|SP-CF-AILTA|SP-SR-LA|MP-CF|all
#                (default: interactive menu)
#   --instance   0-9   (default: 0)
#   --seed       int   (default: 42)
#   --budget     int   (default: 100000 iterations)
#   --analyse    run the Python analysis pipeline after all runs complete
#
# Examples:
#   bash scripts/run_domain.sh --domain SAT --technique all --budget 50000
#   bash scripts/run_domain.sh --domain all --technique SP-CF-LA --analyse

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

JAR="${REPO_ROOT}/build/libs/xai-sphh-0.1.0-SNAPSHOT.jar"
TRACES_DIR="${REPO_ROOT}/data/raw/traces"
TMP_CONFIGS="${REPO_ROOT}/data/tmp_configs"

# ---------------------------------------------------------------------------
# Available domains and techniques
# ---------------------------------------------------------------------------
ALL_DOMAINS=("SAT" "BinPacking" "FlowShop" "TSP" "VRP" "PersonnelScheduling")
ALL_DOMAIN_LABELS=(
    "SAT                  -- Boolean Satisfiability"
    "BinPacking           -- 1-D Bin Packing"
    "FlowShop             -- Permutation Flow Shop Scheduling"
    "TSP                  -- Travelling Salesman Problem"
    "VRP                  -- Vehicle Routing Problem"
    "PersonnelScheduling  -- Personnel Scheduling (Rostering)"
)

ALL_TECHNIQUES=("SP-CF-LA" "SP-CF-AILTA" "SP-SR-LA" "MP-CF")
ALL_TECHNIQUE_LABELS=(
    "SP-CF-LA    -- Single-Point, Choice Function, Late Acceptance"
    "SP-CF-AILTA -- Single-Point, Choice Function, Adaptive Improved Late Acceptance"
    "SP-SR-LA    -- Single-Point, Simple Random, Late Acceptance"
    "MP-CF       -- Multi-Point (population), Choice Function"
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
OPT_DOMAIN=""
OPT_TECHNIQUE=""
OPT_INSTANCE=0
OPT_SEED=42
OPT_SEED_SET=false   # true when --seed was supplied explicitly
OPT_BUDGET=100000
OPT_BUDGET_SET=false   # true when --budget was supplied explicitly
OPT_ANALYSE=false

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)    OPT_DOMAIN="$2";    shift 2 ;;
        --technique) OPT_TECHNIQUE="$2"; shift 2 ;;
        --instance)  OPT_INSTANCE="$2";  shift 2 ;;
        --seed)      OPT_SEED="$2"; OPT_SEED_SET=true; shift 2 ;;
        --budget)    OPT_BUDGET="$2"; OPT_BUDGET_SET=true; shift 2 ;;
        --analyse)   OPT_ANALYSE=true;   shift   ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Run 'bash scripts/run_domain.sh --help' for usage." >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Colour helpers (degrade gracefully if terminal does not support them)
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    BOLD="\033[1m"; RESET="\033[0m"
    GREEN="\033[32m"; CYAN="\033[36m"; YELLOW="\033[33m"; RED="\033[31m"
else
    BOLD=""; RESET=""; GREEN=""; CYAN=""; YELLOW=""; RED=""
fi

header() { printf "\n${BOLD}${CYAN}%s${RESET}\n" "$*"; }
info()   { printf "  ${GREEN}>>>${RESET} %s\n" "$*"; }
warn()   { printf "  ${YELLOW}[WARN]${RESET} %s\n" "$*"; }
err()    { printf "  ${RED}[ERROR]${RESET} %s\n" "$*" >&2; }

# ---------------------------------------------------------------------------
# Interactive menu helpers
# ---------------------------------------------------------------------------
# Result variable used by pick_from_list to avoid stdout-capture problems
# when called inside $().
PICK_RESULT=""

# pick_from_list PROMPT VALUES_ARRAY LABELS_ARRAY
#   VALUES_ARRAY  -- short codes used internally (e.g. "SP-CF-LA")
#   LABELS_ARRAY  -- display strings shown in the menu (parallel to VALUES_ARRAY)
# Result is placed in PICK_RESULT.
pick_from_list() {
    local prompt="$1"
    local -n _values="$2"
    local -n _labels="$3"
    echo ""
    printf "${BOLD}%s${RESET}\n" "${prompt}"
    local i=0
    for label in "${_labels[@]}"; do
        printf "  [%d] %s\n" "$((i+1))" "${label}"
        i=$((i+1))
    done
    printf "  [%d] All\n" "$((i+1))"

    local choice
    while true; do
        read -r -p "  Choose (1-$((i+1))): " choice
        if [[ "${choice}" =~ ^[0-9]+$ ]] && \
           [[ "${choice}" -ge 1 ]] && \
           [[ "${choice}" -le "$((i+1))" ]]; then
            break
        fi
        warn "Please enter a number between 1 and $((i+1))."
    done

    if [[ "${choice}" -eq "$((i+1))" ]]; then
        PICK_RESULT="all"
    else
        PICK_RESULT="${_values[$((choice-1))]}"
    fi
}

# pick_budget prompts the user for an iteration budget.
# Presets cover quick smoke tests up to a full CHeSC-style run.
# Choosing "Custom" allows free entry of any positive integer.
# Result is placed in OPT_BUDGET.
pick_budget() {
    local -a presets=(10000 50000 100000 250000 500000)
    local -a labels=(
        " 10,000  -- quick smoke test   (~1 min)"
        " 50,000  -- short run          (~3 min)"
        "100,000  -- standard run       (~8 min)"
        "250,000  -- extended run       (~20 min)"
        "500,000  -- long run           (~40 min)"
        "Custom   -- enter your own value"
    )
    echo ""
    printf "${BOLD}Select iteration budget:${RESET}\n"
    local i=0
    for lbl in "${labels[@]}"; do
        printf "  [%d] %s\n" "$((i+1))" "${lbl}"
        i=$((i+1))
    done

    local choice
    while true; do
        read -r -p "  Choose (1-${i}): " choice
        if [[ "${choice}" =~ ^[0-9]+$ ]] && \
           [[ "${choice}" -ge 1 ]] && \
           [[ "${choice}" -le "${i}" ]]; then
            break
        fi
        warn "Please enter a number between 1 and ${i}."
    done

    if [[ "${choice}" -eq "${i}" ]]; then
        # Custom entry
        while true; do
            read -r -p "  Enter budget (iterations): " OPT_BUDGET
            if [[ "${OPT_BUDGET}" =~ ^[1-9][0-9]*$ ]]; then
                break
            fi
            warn "Please enter a positive integer."
        done
    else
        OPT_BUDGET="${presets[$((choice-1))]}"
    fi
}

# pick_seed prompts the user for a random seed.
# Common seeds are offered as presets; a custom integer can also be entered.
# Result is placed in OPT_SEED.
pick_seed() {
    local -a presets=(42 0 1 7 123 999)
    local -a labels=(
        " 42  -- default reproducible seed"
        "  0"
        "  1"
        "  7"
        "123"
        "999"
        "Custom -- enter your own value"
    )
    echo ""
    printf "${BOLD}Select random seed:${RESET}\n"
    local i=0
    for lbl in "${labels[@]}"; do
        printf "  [%d] %s\n" "$((i+1))" "${lbl}"
        i=$((i+1))
    done

    local choice
    while true; do
        read -r -p "  Choose (1-${i}): " choice
        if [[ "${choice}" =~ ^[0-9]+$ ]] && \
           [[ "${choice}" -ge 1 ]] && \
           [[ "${choice}" -le "${i}" ]]; then
            break
        fi
        warn "Please enter a number between 1 and ${i}."
    done

    if [[ "${choice}" -eq "${i}" ]]; then
        while true; do
            read -r -p "  Enter seed (non-negative integer): " OPT_SEED
            if [[ "${OPT_SEED}" =~ ^[0-9]+$ ]]; then
                break
            fi
            warn "Please enter a non-negative integer."
        done
    else
        OPT_SEED="${presets[$((choice-1))]}"
    fi
}

# ---------------------------------------------------------------------------
# Resolve domain and technique selections
# ---------------------------------------------------------------------------
if [[ -z "${OPT_DOMAIN}" ]]; then
    pick_from_list "Select a problem domain:" ALL_DOMAINS ALL_DOMAIN_LABELS
    OPT_DOMAIN="${PICK_RESULT}"
fi
if [[ -z "${OPT_TECHNIQUE}" ]]; then
    pick_from_list "Select a hyper-heuristic technique:" ALL_TECHNIQUES ALL_TECHNIQUE_LABELS
    OPT_TECHNIQUE="${PICK_RESULT}"
fi

if [[ "${OPT_BUDGET_SET}" == false ]]; then
    pick_budget
fi
if [[ "${OPT_SEED_SET}" == false ]]; then
    pick_seed
fi

if [[ "${OPT_DOMAIN}" == "all" ]]; then
    DOMAINS=("${ALL_DOMAINS[@]}")
else
    DOMAINS=("${OPT_DOMAIN}")
fi
if [[ "${OPT_TECHNIQUE}" == "all" ]]; then
    TECHNIQUES=("${ALL_TECHNIQUES[@]}")
else
    TECHNIQUES=("${OPT_TECHNIQUE}")
fi

# ---------------------------------------------------------------------------
# Build classes if needed (gradlew run handles the full classpath)
# ---------------------------------------------------------------------------
if [[ ! -f "${JAR}" ]]; then
    header "Building ..."
    ./gradlew classes -q
fi

# ---------------------------------------------------------------------------
# Generate a YAML config for a single (domain, technique, instance, seed) run
# ---------------------------------------------------------------------------
make_config() {
    local technique="$1"
    local domain="$2"
    local instance="$3"
    local seed="$4"
    local budget="$5"
    local out_file="$6"

    local tech_params=""
    case "${technique}" in
        SP-CF-LA|SP-SR-LA)
            tech_params="  listLength: 50"
            ;;
        SP-CF-AILTA)
            tech_params="  totalIterations: ${budget}"
            ;;
        MP-CF)
            tech_params="  populationSize: 10"
            ;;
        SP-CF-SA|SP-SR-SA)
            tech_params="  initialTemp: 0.1\n  decayRate: 0.99"
            ;;
    esac

    cat > "${out_file}" <<YAML
techniqueName: ${technique}
domain: ${domain}
instanceIndex: ${instance}
seed: ${seed}
budgetType: iterations
budgetValue: ${budget}
outputDirectory: ${TRACES_DIR}
techniqueParameters:
$(printf "%b" "${tech_params}")
YAML
}

# ---------------------------------------------------------------------------
# Print a metrics summary for one run from its manifest file
# ---------------------------------------------------------------------------
print_metrics() {
    local manifest="$1"
    python3 - "${manifest}" <<'PYEOF'
import sys, json, datetime

path = sys.argv[1]
try:
    m = json.load(open(path, encoding="utf-8"))
except Exception as e:
    print(f"  (could not read manifest: {e})")
    sys.exit(0)

cfg = m.get("config", {})
start = m.get("startTime", "")
end   = m.get("endTime", "")
stub  = m.get("stub", True)

duration_s = None
if start and end:
    try:
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        t0 = datetime.datetime.strptime(start[:26] + "Z", fmt)
        t1 = datetime.datetime.strptime(end[:26]   + "Z", fmt)
        duration_s = (t1 - t0).total_seconds()
    except Exception:
        pass

print(f"  Technique   : {cfg.get('techniqueName', '?')}")
print(f"  Domain      : {cfg.get('domain', '?')} (instance {cfg.get('instanceIndex', '?')}, seed {cfg.get('seed', '?')})")
print(f"  Budget      : {cfg.get('budgetValue', '?')} {cfg.get('budgetType', 'iterations')}")
print(f"  Final obj.  : {m.get('finalObjective', 'N/A')}")
if duration_s is not None:
    print(f"  Wall time   : {duration_s:.1f}s")
print(f"  Stub run    : {stub}")
if stub:
    print("  [NOTE] Stub run -- no real HyFlex domain was executed.")
PYEOF
}

# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------
header "xaisphh experiment runner"
printf "  Domains    : %s\n" "${DOMAINS[*]}"
printf "  Techniques : %s\n" "${TECHNIQUES[*]}"
printf "  Instance   : %s\n" "${OPT_INSTANCE}"
printf "  Seed       : %s\n" "${OPT_SEED}"
printf "  Budget     : %s iterations\n" "${OPT_BUDGET}"

mkdir -p "${TMP_CONFIGS}" "${TRACES_DIR}"

TOTAL=$(( ${#DOMAINS[@]} * ${#TECHNIQUES[@]} ))
CURRENT=0
FAILED=()
MANIFESTS=()

for domain in "${DOMAINS[@]}"; do
    for technique in "${TECHNIQUES[@]}"; do
        CURRENT=$((CURRENT + 1))
        RUN_ID="${technique}_${domain}_${OPT_INSTANCE}_${OPT_SEED}"
        CONFIG_FILE="${TMP_CONFIGS}/${RUN_ID}.yaml"
        MANIFEST_FILE="${TRACES_DIR}/manifest_${RUN_ID}.json"

        header "[${CURRENT}/${TOTAL}] ${technique} on ${domain} (instance ${OPT_INSTANCE}, seed ${OPT_SEED})"

        make_config "${technique}" "${domain}" "${OPT_INSTANCE}" "${OPT_SEED}" "${OPT_BUDGET}" "${CONFIG_FILE}"

        START_TS=$(date +%s)
        # gradlew run handles the full classpath including dependencies.
        # VFORK is applied via gradle.properties for WSL2 compatibility.
        if ./gradlew run -q --args="${CONFIG_FILE}" 2>&1; then
            END_TS=$(date +%s)
            ELAPSED=$(( END_TS - START_TS ))
            info "Completed in ${ELAPSED}s."
            if [[ -f "${MANIFEST_FILE}" ]]; then
                print_metrics "${MANIFEST_FILE}"
                MANIFESTS+=("${MANIFEST_FILE}")
            else
                warn "Manifest not found at ${MANIFEST_FILE}"
            fi
        else
            err "Run failed: ${technique} on ${domain}"
            FAILED+=("${RUN_ID}")
        fi
    done
done

# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------
if [[ ${#MANIFESTS[@]} -gt 0 ]]; then
    header "Summary table"
    python3 - "${MANIFESTS[@]}" <<'PYEOF'
import sys, json

manifests = sys.argv[1:]
rows = []
for path in manifests:
    try:
        m = json.load(open(path, encoding="utf-8"))
        cfg = m.get("config", {})
        rows.append({
            "technique":  cfg.get("techniqueName", "?"),
            "domain":     cfg.get("domain", "?"),
            "instance":   cfg.get("instanceIndex", "?"),
            "seed":       cfg.get("seed", "?"),
            "budget":     cfg.get("budgetValue", "?"),
            "final_obj":  m.get("finalObjective", float("nan")),
            "stub":       m.get("stub", True),
        })
    except Exception:
        pass

if not rows:
    print("  No results to display.")
    sys.exit(0)

rows.sort(key=lambda r: (r["domain"], r["technique"]))

col_w = {
    "technique": max(len("technique"), max(len(r["technique"]) for r in rows)),
    "domain":    max(len("domain"),    max(len(str(r["domain"])) for r in rows)),
    "instance":  8,
    "seed":      6,
    "final_obj": 10,
    "stub":      5,
}

def row_fmt(r):
    return (
        f"  {str(r['technique']):<{col_w['technique']}}  "
        f"{str(r['domain']):<{col_w['domain']}}  "
        f"{str(r['instance']):>{col_w['instance']}}  "
        f"{str(r['seed']):>{col_w['seed']}}  "
        f"{str(r['final_obj']):>{col_w['final_obj']}}  "
        f"{'Y' if r['stub'] else 'N':>{col_w['stub']}}"
    )

header_line = (
    f"  {'technique':<{col_w['technique']}}  "
    f"{'domain':<{col_w['domain']}}  "
    f"{'instance':>{col_w['instance']}}  "
    f"{'seed':>{col_w['seed']}}  "
    f"{'final_obj':>{col_w['final_obj']}}  "
    f"{'stub':>{col_w['stub']}}"
)
sep = "  " + "-" * (len(header_line) - 2)
print(header_line)
print(sep)
for r in rows:
    print(row_fmt(r))
PYEOF
fi

# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------
if [[ ${#FAILED[@]} -gt 0 ]]; then
    header "Failed runs"
    for run in "${FAILED[@]}"; do
        err "${run}"
    done
fi

# ---------------------------------------------------------------------------
# Optional analysis pipeline
# ---------------------------------------------------------------------------
if [[ "${OPT_ANALYSE}" == true ]]; then
    header "Running analysis pipeline ..."
    python3 -m xaisphh.cli load     --traces "${TRACES_DIR}"     --out data/interim
    python3 -m xaisphh.cli features --interim data/interim        --out data/processed
    python3 -m xaisphh.cli yates    --interim data/interim        --out data/processed/yates
    python3 -m xaisphh.cli train    --processed data/processed    --out results/models --ablation
    python3 -m xaisphh.cli explain  --results results/models      --processed data/processed --out results/explanations
    python3 -m xaisphh.cli report \
        --interim      data/interim \
        --processed    data/processed \
        --models       results/models \
        --explanations results/explanations \
        --out          results/report.pdf
    info "Analysis complete. Report written to results/report.pdf."
fi

header "Done."
