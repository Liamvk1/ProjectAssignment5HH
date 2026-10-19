# Runner Instructions

Step-by-step guide for building the Java experiment runner and executing the full
XAI analysis pipeline from raw traces to publication figures.

> **Other docs:** [README.md](README.md) — project overview |
> [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) — technical reference |
> [docs/system-explainer.pdf](docs/system-explainer.pdf) — plain-English explainer

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

All Gradle commands are run from the **project root** — the folder that contains
`build.gradle`. Open a terminal there before running anything below.

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

### 3.1 Interactive runner (recommended)

```bash
bash scripts/run_domain.sh
```

Presents four menus in sequence:

| Menu | Options |
|------|---------|
| Domain | SAT, BinPacking, FlowShop, TSP, VRP, PersonnelScheduling, or **All** |
| Technique | SP-CF-LA, SP-CF-AILTA, SP-SR-LA, MP-CF, or **All** |
| Budget | 10k / 50k / 100k / 250k / 500k iterations, or Custom |
| Seed | 42 / 0 / 1 / 7 / 123 / 999, or Custom |

After all runs complete, the script prints a summary table of final objective
values and writes all trace files to `data/raw/traces/`.

> **Wall-clock note:** PersonnelScheduling takes 5–8 hours per run at 100k
> iterations. Selecting "All" domains with "All" techniques at 100k iterations
> = 24 runs ≈ 30+ hours total, dominated by PersonnelScheduling.

### 3.2 Config file format (manual runs)

Each experiment is described by a YAML config file:

```yaml
techniqueName: SP-CF-LA       # [SP|MP]-[CF|SR][-acceptance]
domain: SAT                   # SAT | BinPacking | FlowShop | TSP | VRP | PersonnelScheduling
instanceIndex: 0              # 0-9
seed: 42
budgetType: iterations        # iterations | time (milliseconds)
budgetValue: 100000
outputDirectory: data/raw/traces
techniqueParameters:
  listLength: 50              # Late Acceptance list length (default 50)
  # populationSize: 10        # MP population size (default 10)
  # budgetScaling: per_member # multiply budget by population size (MP only)
  # initialTemp: 1000.0       # Simulated Annealing start temperature
  # decayRate: 0.99           # Simulated Annealing cooling factor
  # totalIterations: 100000   # AILTA decay calibration (= budgetValue)
```

**Technique name format**: `[SP|MP]-[CF|SR][-acceptance]`

| Component | Options |
|-----------|---------|
| Mode | `SP` = single-point, `MP` = multi-point (population) |
| Selection | `CF` = Choice Function, `SR` = Simple Random |
| Acceptance | `LA`, `AILTA`, `SA`, `IOE`, `NAIVE` (SP only; MP has no acceptance suffix) |

### 3.3 Run a single config manually

```bash
./gradlew run --args="config/experiments/sp-cf-la.yaml"
```

> **Important:** Do **not** use `java -jar build/libs/*.jar`. The thin JAR does
> not include runtime dependencies (snakeyaml, jackson, etc.) and will fail with
> `NoClassDefFoundError`. Always use `./gradlew run --args=`.

Each run writes two files to `outputDirectory`:
- `trace_<technique>_<domain>_<instance>_<seed>.csv` — per-iteration trace
- `manifest_<technique>_<domain>_<instance>_<seed>.json` — run metadata

### 3.4 Create a new experiment config

```bash
cp config/experiments/sp-cf-la.yaml config/experiments/my-experiment.yaml
# edit techniqueName, domain, instanceIndex, seed, budgetValue, etc.
./gradlew run --args="config/experiments/my-experiment.yaml"
```

---

## Part 4 — Python Analysis Pipeline

All pipeline stages are run from the **project root** with `python3 -m xaisphh.cli`.

### Stage 1 — Load traces

Reads all CSV trace files and validates them against the schema. Produces
`traces.parquet` and `run_metadata.parquet` for downstream stages.

```bash
python3 -m xaisphh.cli load \
    --traces data/raw/traces/ \
    --out    data/interim/
```

Output: `data/interim/traces.parquet`, `data/interim/run_metadata.parquet`

Options:
- `--allow-mixed` — allow stub and real HyFlex runs in the same analysis

### Stage 2 — Build feature matrix

Selects `feat_*` columns as predictors and the `accepted` column as the binary
target. Fills missing values with -1.0 (sentinel for "not applicable").

```bash
python3 -m xaisphh.cli features \
    --interim data/interim/ \
    --out     data/processed/
```

Output: `data/processed/X.parquet`, `data/processed/y.parquet`,
`data/processed/technique.parquet`

Options:
- `--keep-scores` — also include `score_*` selector score columns in X

### Stage 3 — Yates reference measures

Computes log returns with clipping, percentile ranks, Spearman footrule
distances, and acceptance-rate vs. progress curves.

```bash
python3 -m xaisphh.cli yates \
    --interim data/interim/ \
    --out     results/yates/
```

Output: `log_returns_by_heuristic.csv`, `percentile_ranks.csv`,
`footrule_distances.csv`, `acceptance_rate_by_progress.csv`

Options:
- `--clip-low -10.0` / `--clip-high 10.0` (default) — log-return clipping bounds
- `--divergence-factor 2.0` (default) — flag heuristics with mean/median ratio > this

### Stage 4 — Train surrogate

By default trains one surrogate per technique (not pooled). Constant features
within each technique are automatically dropped. Evaluates faithfulness with
5-fold stratified cross-validation.

```bash
python3 -m xaisphh.cli train \
    --processed data/processed/ \
    --out       results/models/
```

Output per technique: `results/models/<technique>/surrogate.joblib`,
`results/models/<technique>/faithfulness_metrics.json`

Cross-technique summary: `results/models/technique_comparison.csv`

Options:
- `--model-type gradient_boosting` (default) | `random_forest` | `logistic_regression`
- `--seed 42` (default)
- `--ablation` — also run identity/class ablation study per technique
- `--pooled` — train a single pooled model instead of per-technique models

### Stage 5 — Generate explanations

Computes global SHAP feature importance per technique, SHAP pairwise interaction
values (subsampled), and a systematic LIME grid over 50 evenly-spaced decision
points per technique.

```bash
python3 -m xaisphh.cli explain \
    --results   results/models/ \
    --processed data/processed/ \
    --out       results/explanations/
```

Output per technique (`results/explanations/<technique>/`):
- `shap_global_importance.csv` — mean |SHAP| per feature
- `shap_summary_plot.pdf` — SHAP beeswarm plot
- `shap_interaction_heatmap.pdf` — pairwise interaction heatmap
- `lime_grid.csv` — LIME explanations at 50 evenly-spaced decision points
- `lime_condition_frequency.csv` — most frequent LIME conditions
- `lime_condition_frequency.pdf` — bar chart of top conditions

Cross-technique summary: `results/explanations/shap_comparison_by_technique.csv`

Options:
- `--n-lime-grid 50` (default) — number of evenly-spaced LIME grid points
- `--n-interactions 2000` (default) — samples used for interaction values
- `--pooled` — explain pooled model instead of per-technique models

### Stage 6 — Generate figures

Produces publication-ready PDF figures: best-so-far convergence curves and
per-technique SHAP global importance bar charts.

```bash
python3 -m xaisphh.cli figures \
    --results results/explanations/ \
    --interim data/interim/ \
    --out     results/figures/
```

Output: `results/figures/convergence.pdf`,
`results/figures/shap_importance_<technique>.pdf`

### Stage 7 — Generate report

Assembles all pipeline outputs into a multi-page PDF report.

```bash
python3 -m xaisphh.cli report \
    --interim      data/interim/ \
    --processed    data/processed/ \
    --models       results/models/ \
    --explanations results/explanations/ \
    --out          results/report.pdf
```

Output: `results/report.pdf` (also saves a timestamped copy alongside it).

---

## Part 5 — Full Pipeline (Quick Reference)

Run these commands in order after placing traces in `data/raw/traces/`:

```bash
python3 -m xaisphh.cli load     --traces data/raw/traces/  --out data/interim/
python3 -m xaisphh.cli features --interim data/interim/    --out data/processed/
python3 -m xaisphh.cli yates    --interim data/interim/    --out results/yates/
python3 -m xaisphh.cli train    --processed data/processed/ --out results/models/ --ablation
python3 -m xaisphh.cli explain  --results results/models/ --processed data/processed/ --out results/explanations/
python3 -m xaisphh.cli figures  --results results/explanations/ --interim data/interim/ --out results/figures/
python3 -m xaisphh.cli report   --interim data/interim/ --processed data/processed/ --models results/models/ --explanations results/explanations/ --out results/report.pdf
```

> **Tip:** `bash scripts/test_pipeline.sh` runs all stages plus Java tests in one
> shot and prints a formatted summary of all key outputs.

---

## Directory Layout

```
xai-sphh/
├── build.gradle                  # Gradle build script
├── config/
│   ├── features.yaml             # Feature set configuration
│   └── experiments/              # Experiment YAML configs
│       ├── baseline.yaml         # SP-SR-LA (baseline)
│       ├── sp-cf-la.yaml         # SP-CF-LA
│       ├── sp-cf-ailta.yaml      # SP-CF-AILTA
│       └── mp-cf.yaml            # MP-CF
├── data/
│   ├── raw/traces/               # Java output: trace CSVs and manifest JSONs
│   ├── interim/                  # Stage 1 output: traces.parquet, run_metadata.parquet
│   └── processed/                # Stage 2 output: X.parquet, y.parquet, technique.parquet
├── java/src/
│   ├── main/java/                # Java source
│   ├── stubs/java/               # HyFlex API stubs (compile fallback)
│   └── test/java/                # Unit tests (26 tests)
├── lib/hyflex/                   # Vendored HyFlex CHeSC jars (place here manually)
├── python/
│   └── src/xaisphh/              # Python package source
├── results/
│   ├── models/                   # Per-technique surrogates and faithfulness metrics
│   │   └── <technique>/          # One subdirectory per technique
│   ├── explanations/             # Per-technique SHAP and LIME outputs
│   │   └── <technique>/
│   ├── yates/                    # Reference measure tables (CSV)
│   ├── figures/                  # Publication PDF figures
│   └── report.pdf                # Generated PDF report
├── docs/
│   ├── trace-schema.md           # Trace file column specification (v2)
│   └── design-decisions.md       # Design decision log (DD-01 through DD-28)
└── scripts/
    ├── run_domain.sh             # Interactive experiment runner
    └── test_pipeline.sh          # Full end-to-end smoke test
```

---

## Troubleshooting

**`No HyFlex jars found in lib/hyflex/`**
Place `chesc-fixed-no-ps.jar` and `chesc-ps.jar` in `lib/hyflex/` before running
experiments. The build will warn but still succeed using stubs.

**`java -jar build/libs/*.jar` fails with `NoClassDefFoundError`**
The JAR built by `./gradlew jar` is a thin JAR (no bundled dependencies). Always
run experiments with `./gradlew run --args="config/experiments/sp-cf-la.yaml"`.

**`Unknown domain: '...'`**
Domain names are case-sensitive. Use exactly: `SAT`, `BinPacking`, `FlowShop`,
`TSP`, `VRP`, `PersonnelScheduling`.

**`Unknown acceptance component '...'`**
Check the technique name format. Valid acceptance suffixes: `LA`, `AILTA`, `SA`,
`IOE`, `NAIVE`. MP techniques take no acceptance suffix (e.g. `MP-CF`, not `MP-CF-LA`).

**`No feature columns found`**
Ensure the trace CSV was produced by the current Java runner (schema v2). Old
traces from a previous schema version must be regenerated.

**`features` reads from `data/interim/` but the directory does not exist**
The `load` stage outputs to `data/interim/`, not `data/processed/`. Run
`load --out data/interim/` first.

**Out-of-memory during `train` on large datasets**
Reduce the dataset size by running fewer experiments, or switch to
`--model-type random_forest` which is more memory-efficient than gradient boosting.

**SHAP interaction values taking too long**
Pass `--n-interactions 1000` (or lower) to the `explain` command to subsample
fewer rows for the interaction computation.

**LIME grid is empty for a technique**
This can occur when class imbalance is severe (e.g. >95% one class). The local
neighbourhood is dominated by the majority class and the linear approximation
has near-zero weights. Use `--n-lime-grid` with a larger value, or inspect
`lime_condition_frequency.csv` for the techniques that do produce conditions.
