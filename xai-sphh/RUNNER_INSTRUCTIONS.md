# Runner Instructions

Step-by-step guide for building the Java experiment runner and executing the full
XAI analysis pipeline from raw traces to publication figures.

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Java (JDK) | 21+ | `java --version` |
| Python | 3.11+ | `python3 --version` |
| HyFlex CHeSC jars | — | must be in `lib/hyflex/` |

The HyFlex jars required are:
- `lib/hyflex/chesc-fixed-no-ps.jar` — SAT, BinPacking, FlowShop, TSP, VRP domains
- `lib/hyflex/chesc-ps.jar` — PersonnelScheduling domain

> Without the jars the project still compiles (using API stubs) and all unit tests
> pass, but experiments cannot be run.

---

## Part 1 — Java Build

All Gradle commands are run from the **project root** (where `build.gradle` lives):

```
/mnt/c/Users/Liamv/OneDrive/Tuks/honours/COS790/xai-sphh/
```

### 1.1 Compile

```bash
./gradlew compileJava
```

### 1.2 Run unit tests

```bash
./gradlew test
```

Expected: 26 tests pass, 0 fail. Test reports are written to
`build/reports/tests/test/index.html`.

### 1.3 Build the fat jar

```bash
./gradlew jar
```

Output: `build/libs/xai-sphh-0.1.0-SNAPSHOT.jar`

---

## Part 2 — Python Setup

```bash
pip install -e python/ --break-system-packages
```

Verify the CLI is available:

```bash
python3 -m xaisphh.cli --help
```

---

## Part 3 — Running Experiments

Each experiment is described by a YAML config file in `config/experiments/`.

### 3.1 Config file format

```yaml
techniqueName: SP-SR-LA       # [SP|MP]-[CF|SR][-acceptance]
domain: SAT                   # SAT | BinPacking | FlowShop | TSP | VRP | PersonnelScheduling
instanceIndex: 0              # 0-9
seed: 42
budgetType: iterations        # iterations | time (milliseconds)
budgetValue: 100000
outputDirectory: data/raw/traces
techniqueParameters:
  listLength: 50              # Late Acceptance list length (default 50)
  # initialTemp: 1000.0       # Simulated Annealing start temperature
  # decayRate: 0.99           # Simulated Annealing cooling factor
  # totalIterations: 100000   # AILTA decay calibration (= budgetValue for iteration budgets)
  # populationSize: 10        # MP population size (default 10)
```

**Technique name format**: `[SP|MP]-[CF|SR][-acceptance]`

| Component | Options |
|-----------|---------|
| Mode | `SP` = single-point, `MP` = multi-point (population) |
| Selection | `CF` = Choice Function, `SR` = Simple Random |
| Acceptance | `LA` = Late Acceptance, `AILTA`, `SA` = Simulated Annealing, `IOE` = Improving-or-Equal, `NAIVE` |

MP techniques have no acceptance suffix (replacement rule acts as acceptance).

### 3.2 Run a single experiment

```bash
./gradlew run --args="config/experiments/baseline.yaml"
```

Or using the jar directly:

```bash
java -jar build/libs/xai-sphh-0.1.0-SNAPSHOT.jar config/experiments/baseline.yaml
```

Each run writes two files to `outputDirectory`:
- `trace_<technique>_<domain>_<instance>_<seed>.csv` — per-iteration trace (35+ columns)
- `manifest_<technique>_<domain>_<instance>_<seed>.json` — run metadata

### 3.3 Run all four baseline configurations

```bash
./gradlew run --args="config/experiments/baseline.yaml"
./gradlew run --args="config/experiments/sp-cf-la.yaml"
./gradlew run --args="config/experiments/sp-cf-ailta.yaml"
./gradlew run --args="config/experiments/mp-cf.yaml"
```

Each takes approximately 5-7 minutes for 100,000 iterations on the SAT domain.

### 3.4 Create a new experiment config

Copy an existing config and edit the fields:

```bash
cp config/experiments/baseline.yaml config/experiments/my-experiment.yaml
# edit techniqueName, domain, instanceIndex, seed, etc.
./gradlew run --args="config/experiments/my-experiment.yaml"
```

---

## Part 4 — Python Analysis Pipeline

All six stages are run from the **project root** with `python3 -m xaisphh.cli`.

### Stage 1 — Load traces

Reads all CSV trace files and validates them against the schema. Produces a
single Parquet file for downstream stages.

```bash
python3 -m xaisphh.cli load \
    --traces data/raw/traces/ \
    --out    data/processed/
```

Output: `data/processed/traces.parquet`

### Stage 2 — Build feature matrix

Selects `feat_*` columns as predictors and the `accepted` column as the binary
target. Fills missing values with -1.0 (sentinel for "not applicable").

```bash
python3 -m xaisphh.cli features \
    --interim data/processed/ \
    --out     data/processed/
```

Output: `data/processed/X.parquet`, `data/processed/y.parquet`

Options:
- `--keep-scores` — also include `score_*` selector score columns in X

### Stage 3 — Yates reference measures

Computes log returns, percentile ranks, and Spearman footrule distances
comparing early vs. late search heuristic rankings.

```bash
python3 -m xaisphh.cli yates \
    --interim data/processed/ \
    --out     results/yates/
```

Output: `log_returns_by_heuristic.csv`, `percentile_ranks.csv`,
`footrule_distances.csv`

### Stage 4 — Train surrogate

Fits a gradient boosting classifier on the feature matrix. Evaluates
faithfulness with 5-fold stratified cross-validation.

```bash
python3 -m xaisphh.cli train \
    --processed data/processed/ \
    --out       results/models/
```

Output: `results/models/surrogate.joblib`,
`results/models/faithfulness_metrics.json`

Options:
- `--model-type gradient_boosting` (default) | `random_forest` | `logistic_regression`
- `--seed 42` (default)

### Stage 5 — Generate explanations

Computes global SHAP feature importance, SHAP pairwise interaction values
(subsampled), and LIME local explanations for selected instances.

```bash
python3 -m xaisphh.cli explain \
    --results   results/models/ \
    --processed data/processed/ \
    --out       results/explanations/
```

Output:
- `shap_global_importance.csv` — mean |SHAP| per feature
- `shap_summary_plot.pdf` — SHAP beeswarm plot
- `shap_interaction_heatmap.pdf` — pairwise interaction heatmap
- `lime/lime_instance_<n>.pdf` — local LIME explanations

Options:
- `--n-lime-instances 5` (default) — number of instances to explain with LIME
- `--n-interactions 2000` (default) — samples used for interaction values

### Stage 6 — Generate figures

Produces publication-ready PDF figures: best-so-far convergence curves and
a SHAP global importance bar chart.

```bash
python3 -m xaisphh.cli figures \
    --results results/explanations/ \
    --interim data/processed/ \
    --out     results/figures/
```

Output: `results/figures/convergence.pdf`,
`results/figures/shap_importance.pdf`

---

## Part 5 — Full Pipeline (Quick Reference)

Run these commands in order after placing traces in `data/raw/traces/`:

```bash
python3 -m xaisphh.cli load     --traces data/raw/traces/  --out data/processed/
python3 -m xaisphh.cli features --interim data/processed/  --out data/processed/
python3 -m xaisphh.cli yates    --interim data/processed/  --out results/yates/
python3 -m xaisphh.cli train    --processed data/processed/ --out results/models/
python3 -m xaisphh.cli explain  --results results/models/ --processed data/processed/ --out results/explanations/
python3 -m xaisphh.cli figures  --results results/explanations/ --interim data/processed/ --out results/figures/
```

---

## Directory Layout

```
xai-sphh/
├── build.gradle                  # Gradle build script
├── config/
│   └── experiments/              # Experiment YAML configs
│       ├── baseline.yaml         # SP-SR-LA (baseline)
│       ├── sp-cf-la.yaml         # SP-CF-LA
│       ├── sp-cf-ailta.yaml      # SP-CF-AILTA
│       └── mp-cf.yaml            # MP-CF
├── data/
│   ├── raw/traces/               # Java output: trace CSVs and manifest JSONs
│   └── processed/                # Python stage 1-2 output: Parquet files
├── java/src/
│   ├── main/java/                # Java source
│   ├── stubs/java/               # HyFlex API stubs (compile fallback)
│   └── test/java/                # Unit tests
├── lib/hyflex/                   # Vendored HyFlex CHeSC jars (place here manually)
├── python/
│   └── src/xaisphh/              # Python package source
└── results/
    ├── models/                   # Surrogate model and faithfulness metrics
    ├── explanations/             # SHAP and LIME outputs
    ├── yates/                    # Reference measure tables
    └── figures/                  # Publication PDF figures
```

---

## Troubleshooting

**`No HyFlex jars found in lib/hyflex/`**
Place `chesc-fixed-no-ps.jar` and `chesc-ps.jar` in `lib/hyflex/` before running
experiments. The build will warn but still succeed using stubs.

**`Unknown domain: '...'`**
Domain names are case-sensitive. Use exactly: `SAT`, `BinPacking`, `FlowShop`,
`TSP`, `VRP`, `PersonnelScheduling`.

**`Unknown acceptance component '...'`**
Check the technique name format. Valid acceptance suffixes: `LA`, `AILTA`, `SA`,
`IOE`, `NAIVE`. MP techniques take no acceptance suffix (e.g. `MP-CF`, not `MP-CF-LA`).

**`No feature columns found`**
Ensure the trace CSV was produced by the current Java runner (schema v2). Old
traces from a previous schema version must be regenerated.

**`X shape: (0, 16)` — zero rows after features stage**
This should not occur with the current code. If it does, check that `X.parquet`
was produced by `features` and that the traces contain `feat_*` columns.

**Out-of-memory during `train` on large datasets**
Reduce the dataset size by running fewer experiments, or switch to
`--model-type random_forest` which is more memory-efficient than gradient boosting.

**SHAP interaction values taking too long**
Pass `--n-interactions 1000` (or lower) to the `explain` command to subsample
fewer rows for the interaction computation.
