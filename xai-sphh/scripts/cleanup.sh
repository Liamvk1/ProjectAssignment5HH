#!/usr/bin/env bash
# ===========================================================================
#  XAI-SPHH Data Cleanup
#
#  Usage:
#    /bin/bash scripts/cleanup.sh
# ===========================================================================
set -eu
cd "$(dirname "$0")/.."

echo "============================================"
echo "  XAI-SPHH Cleanup"
echo "============================================"
echo ""
echo "  What do you want to clean?"
echo ""
echo "  1) a4-traces      Assessment 4 traces (data/raw/traces/)"
echo "  2) a5-traces      Assessment 5 traces (results/a5/traces/)"
echo "  3) a5-all         All Assessment 5 output (results/a5/)"
echo "  4) a5-analysis    A5 analysis only, keep traces (results/a5/statistics, shap, figures)"
echo "  5) convergence    Convergence results (results/budgets/)"
echo "  6) old-results    Old Assessment 4 results (results/models, explanations, yates)"
echo "  7) tmp-configs    Temporary configs (data/tmp_configs/)"
echo "  8) everything     All generated data (keeps source code and config)"
echo "  9) status         Show disk usage of each directory"
echo ""
printf "  Select [1-9]: "
read -r CHOICE

confirm() {
    local target="$1"
    local count
    if [ -d "$target" ]; then
        count=$(find "$target" -type f 2>/dev/null | wc -l)
    else
        count=0
    fi
    echo ""
    echo "  Target:  $target"
    echo "  Files:   $count"
    if [ -d "$target" ]; then
        echo "  Size:    $(du -sh "$target" 2>/dev/null | cut -f1)"
    fi
    echo ""
    printf "  Are you sure? [y/N]: "
    read -r YN
    case "$YN" in
        y|Y|yes|YES) return 0 ;;
        *) echo "  Cancelled."; return 1 ;;
    esac
}

do_clean() {
    local target="$1"
    local label="$2"
    if [ ! -d "$target" ]; then
        echo "  Directory $target does not exist. Nothing to clean."
        return
    fi
    if confirm "$target"; then
        rm -rf "$target"
        mkdir -p "$target"
        echo "  Cleaned: $label"
    fi
}

case "$CHOICE" in
    1) do_clean "data/raw/traces" "Assessment 4 traces" ;;
    2) do_clean "results/a5/traces" "Assessment 5 traces" ;;
    3) do_clean "results/a5" "All Assessment 5 output" ;;
    4)
        for d in results/a5/statistics results/a5/figures results/a5/shap; do
            if [ -d "$d" ]; then
                do_clean "$d" "$d"
            fi
        done
        ;;
    5) do_clean "results/budgets" "Convergence results" ;;
    6)
        for d in results/models results/explanations results/yates results/explain; do
            if [ -d "$d" ]; then
                do_clean "$d" "$d"
            fi
        done
        ;;
    7) do_clean "data/tmp_configs" "Temporary configs" ;;
    8)
        echo ""
        echo "  This will delete ALL generated data:"
        echo "    - data/raw/traces/"
        echo "    - data/tmp_configs/"
        echo "    - results/"
        echo ""
        printf "  Type 'DELETE ALL' to confirm: "
        read -r CONFIRM
        if [ "$CONFIRM" = "DELETE ALL" ]; then
            rm -rf data/raw/traces data/tmp_configs results
            mkdir -p data/raw/traces results
            echo "  All generated data deleted."
        else
            echo "  Cancelled."
        fi
        ;;
    9)
        echo ""
        echo "  Directory                          Files    Size"
        echo "  -------------------------------------------------"
        for d in \
            data/raw/traces \
            data/tmp_configs \
            results/a5/traces \
            results/a5/configs \
            results/a5/statistics \
            results/a5/figures \
            results/a5/shap \
            results/budgets \
            results/models \
            results/explanations \
            results/yates \
            results/explain; do
            if [ -d "$d" ]; then
                COUNT=$(find "$d" -type f 2>/dev/null | wc -l)
                SIZE=$(du -sh "$d" 2>/dev/null | cut -f1)
                printf "  %-35s %5d    %s\n" "$d" "$COUNT" "$SIZE"
            fi
        done
        echo ""
        TOTAL=$(du -sh results 2>/dev/null | cut -f1)
        echo "  Total results/:                              $TOTAL"
        ;;
    *) echo "  Invalid choice." ;;
esac
