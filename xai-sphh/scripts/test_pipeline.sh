#!/usr/bin/env bash
# test_pipeline.sh
# Runs the full xaisphh analysis pipeline and prints a summary of key outputs.
# Run from the xai-sphh/ directory: bash scripts/test_pipeline.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=========================================="
echo "  xaisphh pipeline smoke test"
echo "  Working directory: $REPO_ROOT"
echo "=========================================="

# ---------------------------------------------------------------------------
# Java tests
# ---------------------------------------------------------------------------
echo ""
echo "[1/8] Running Java tests ..."
./gradlew test
echo "  Java tests: PASSED"

# ---------------------------------------------------------------------------
# Python tests
# ---------------------------------------------------------------------------
echo ""
echo "[2/8] Running Python tests ..."
python3 -m pytest python/tests/ -q
echo "  Python tests: PASSED"

# ---------------------------------------------------------------------------
# Stage: load
# ---------------------------------------------------------------------------
echo ""
echo "[3/8] Loading traces and manifests ..."
python3 -m xaisphh.cli load \
  --traces data/raw/traces \
  --out    data/interim

echo ""
echo "  run_metadata.parquet contents:"
python3 - <<'PYEOF'
import pandas as pd
meta = pd.read_parquet("data/interim/run_metadata.parquet")
print(meta.to_string(index=False))
PYEOF

# ---------------------------------------------------------------------------
# Stage: features
# ---------------------------------------------------------------------------
echo ""
echo "[4/8] Assembling feature matrix ..."
python3 -m xaisphh.cli features \
  --interim data/interim \
  --out     data/processed

echo ""
echo "  Feature matrix shape:"
python3 - <<'PYEOF'
import pandas as pd
X = pd.read_parquet("data/processed/X.parquet")
y = pd.read_parquet("data/processed/y.parquet")
t = pd.read_parquet("data/processed/technique.parquet")
print(f"    X: {X.shape}, y: {y.shape}")
print(f"    Techniques: {sorted(t['technique'].unique())}")
print(f"    Acceptance rate: {y['accepted'].mean():.3f}")
PYEOF

# ---------------------------------------------------------------------------
# Stage: yates
# ---------------------------------------------------------------------------
echo ""
echo "[5/8] Running yates reference measures ..."
python3 -m xaisphh.cli yates \
  --interim data/interim \
  --out     data/processed/yates

echo ""
echo "  Log-return stats by heuristic:"
python3 - <<'PYEOF'
import pandas as pd
df = pd.read_csv("data/processed/yates/log_returns_by_heuristic.csv")
print(df.to_string(index=False))
PYEOF

echo ""
echo "  Diagnostics:"
if [ -f data/processed/yates/log_return_diagnostics.txt ] && \
   [ -s data/processed/yates/log_return_diagnostics.txt ]; then
  cat data/processed/yates/log_return_diagnostics.txt
else
  echo "    (none -- no divergent heuristics detected)"
fi

# ---------------------------------------------------------------------------
# Stage: train (per-technique + ablation)
# ---------------------------------------------------------------------------
echo ""
echo "[6/8] Training per-technique surrogates (with ablation) ..."
python3 -m xaisphh.cli train \
  --processed data/processed \
  --out       results/models \
  --ablation

echo ""
echo "  Technique comparison:"
python3 - <<'PYEOF'
import pandas as pd, os
p = "results/models/technique_comparison.csv"
if os.path.exists(p):
    df = pd.read_csv(p)
    print(df.to_string(index=False))
else:
    print("  (technique_comparison.csv not found)")
PYEOF

echo ""
echo "  Dropped features and faithfulness per technique:"
python3 - <<'PYEOF'
import json, os, re
_UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
models_dir = "results/models"
for tech in sorted(os.listdir(models_dir)):
    if _UUID.match(tech):
        continue  # skip stale UUID-named directories from pre-fix runs
    metrics_path = os.path.join(models_dir, tech, "faithfulness_metrics.json")
    if not os.path.isfile(metrics_path):
        continue
    m = json.load(open(metrics_path))
    dropped = m.get("dropped_features", [])
    print(f"  {tech}:")
    print(f"    accuracy={m.get('accuracy', float('nan')):.4f}, "
          f"roc_auc={m.get('roc_auc', float('nan')):.4f}, "
          f"n_features={m.get('n_features_used', '?')}")
    print(f"    dropped={dropped}")
PYEOF

echo ""
echo "  Ablation results per technique:"
python3 - <<'PYEOF'
import pandas as pd, os, re
_UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
models_dir = "results/models"
for tech in sorted(os.listdir(models_dir)):
    if _UUID.match(tech):
        continue  # skip stale UUID-named directories from pre-fix runs
    abl_path = os.path.join(models_dir, tech, "ablation_results.csv")
    if not os.path.isfile(abl_path):
        continue
    df = pd.read_csv(abl_path)
    print(f"  {tech}:")
    print(df[["variant","n_features","accuracy","roc_auc"]].to_string(index=False))
PYEOF

# ---------------------------------------------------------------------------
# Stage: explain
# ---------------------------------------------------------------------------
echo ""
echo "[7/8] Generating explanations (SHAP + LIME grid) ..."
python3 -m xaisphh.cli explain \
  --results   results/models \
  --processed data/processed \
  --out       results/explanations

echo ""
echo "  SHAP cross-technique comparison (top features):"
python3 - <<'PYEOF'
import pandas as pd, os
p = "results/explanations/shap_comparison_by_technique.csv"
if os.path.exists(p):
    df = pd.read_csv(p)
    pivot = df.pivot_table(
        index="feature", columns="technique", values="mean_abs_shap", aggfunc="mean"
    ).round(4)
    print(pivot.to_string())
else:
    print("  (shap_comparison_by_technique.csv not found)")
PYEOF

echo ""
echo "  LIME condition frequency (top 5 per technique):"
python3 - <<'PYEOF'
import pandas as pd, os, re
_UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
for tech in sorted(os.listdir("results/explanations")):
    if _UUID.match(tech):
        continue  # skip stale UUID-named directories from pre-fix runs
    freq_path = os.path.join("results/explanations", tech, "lime_condition_frequency.csv")
    if not os.path.isfile(freq_path):
        continue
    df = pd.read_csv(freq_path)
    print(f"  {tech} (top 5 conditions overall):")
    top = df.nlargest(5, "count")[["condition","count","mean_weight","positive_fraction"]]
    print(top.to_string(index=False))
PYEOF

# ---------------------------------------------------------------------------
# Stage: figures
# ---------------------------------------------------------------------------
echo ""
echo "[8/8] Generating figures ..."
python3 -m xaisphh.cli figures \
  --results results/explanations \
  --interim data/interim \
  --out     results/figures

echo ""
echo "  Output files:"
find results/figures results/explanations results/models data/processed/yates \
  -name "*.pdf" -o -name "*.csv" -o -name "*.json" 2>/dev/null \
  | sort | sed 's|^|    |'

# ---------------------------------------------------------------------------
# Stage: report
# ---------------------------------------------------------------------------
echo ""
echo "[+] Generating PDF report ..."
python3 -m xaisphh.cli report \
  --interim      data/interim \
  --processed    data/processed \
  --models       results/models \
  --explanations results/explanations \
  --out          results/report.pdf

echo ""
echo "=========================================="
echo "  Pipeline complete. All stages passed."
echo "  Report: results/report.pdf"
echo "=========================================="
