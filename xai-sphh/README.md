# XAI for Cross-Domain Selection Perturbative Hyper-Heuristics

This project applies Explainable AI (XAI) to understand how selection perturbative
hyper-heuristics make decisions across six different problem domains. The Java side
runs experiments and records every decision made; the Python side analyses those
recordings and explains them using SHAP and LIME.

---

## Documentation — Start Here

| Document | What it covers |
|----------|---------------|
| **[RUNNER_INSTRUCTIONS.md](RUNNER_INSTRUCTIONS.md)** | How to build and run the project step by step |
| **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** | Full technical reference — every file, every component, how they connect |
| **[docs/system-explainer.pdf](docs/system-explainer.pdf)** | Plain-English explanation of how the whole system works (high and low level) |
| **[docs/trace-schema.md](docs/trace-schema.md)** | Exact column specification for the trace CSV files |
| **[docs/design-decisions.md](docs/design-decisions.md)** | Rationale behind every major design choice |

---

## Quick Start

### Prerequisites

| Tool | Required version | Check |
|------|-----------------|-------|
| Java JDK | 21 or later | `java --version` |
| Python | 3.11 or later | `python3 --version` |
| HyFlex jars | CHeSC 2011 | must be in `lib/hyflex/` |

Two HyFlex jars must be placed in `lib/hyflex/` before running experiments:
- `chesc-fixed-no-ps.jar` — SAT, BinPacking, FlowShop, TSP, VRP
- `chesc-ps.jar` — PersonnelScheduling

### 1. Build and test

```bash
./gradlew build
```

Expected: 26 Java tests pass, BUILD SUCCESSFUL.

### 2. Install the Python package

```bash
pip install -e python/ --break-system-packages
```

### 3. Run an experiment

**Interactive runner (recommended):**

```bash
bash scripts/run_domain.sh
```

Presents menus to choose domain (or all six), technique (or all four), iteration
budget, and random seed. Runs the selected combinations, prints a summary table of
final objective values, and writes trace files to `data/raw/traces/`.

**Single config (manual):**

```bash
./gradlew run --args="config/experiments/sp-cf-la.yaml"
```

Trace files are written to `data/raw/traces/`.

### 4. Run the full analysis pipeline

```bash
python3 -m xaisphh.cli load     --traces data/raw/traces/  --out data/processed/
python3 -m xaisphh.cli features --interim data/processed/  --out data/processed/
python3 -m xaisphh.cli yates    --interim data/processed/  --out results/yates/
python3 -m xaisphh.cli train    --processed data/processed/ --out results/models/
python3 -m xaisphh.cli explain  --results results/models/ --processed data/processed/ --out results/explanations/
python3 -m xaisphh.cli figures  --results results/explanations/ --interim data/processed/ --out results/figures/
```

---

## How It Works (One Paragraph)

A hyper-heuristic sits above a set of low-level problem-solving tools and decides
at each step which tool to use and whether to keep the result. It runs on real
benchmark problems from six domains — SAT, Bin Packing, Flow Shop, TSP, VRP, and
Personnel Scheduling — but never sees the actual problem data; it only ever receives
an objective score. This makes it a cross-domain solver. Every decision is written
to a trace file. A surrogate machine learning model is trained on those traces, then
explained with SHAP (which features matter globally?) and LIME (why was this specific
decision made?). See **[docs/system-explainer.pdf](docs/system-explainer.pdf)** for
a full plain-English walkthrough with diagrams.

---

## Experiment Configurations

Four baseline configurations are in `config/experiments/`:

| File | Technique | Description |
|------|-----------|-------------|
| `baseline.yaml` | SP-SR-LA | Simple Random + Late Acceptance. The baseline. |
| `sp-cf-la.yaml` | SP-CF-LA | Choice Function + Late Acceptance. Primary technique. |
| `sp-cf-ailta.yaml` | SP-CF-AILTA | Choice Function + Adaptive ILTA acceptance. |
| `mp-cf.yaml` | MP-CF | Population search + Choice Function. |

To run a different domain or instance, copy any config and change `domain` and
`instanceIndex`. Available domains: `SAT`, `BinPacking`, `FlowShop`, `TSP`,
`VRP`, `PersonnelScheduling`. Each has 10 instances (index 0–9).

---

## Repository Layout

```
xai-sphh/
├── README.md                       This file — start here
├── RUNNER_INSTRUCTIONS.md          Step-by-step build and run guide
├── IMPLEMENTATION_GUIDE.md         Full technical reference
│
├── build.gradle                    Gradle build configuration
├── gradlew / gradlew.bat           Gradle wrapper (no local install needed)
│
├── lib/hyflex/                     Place HyFlex CHeSC jars here
│
├── config/
│   ├── features.yaml               Feature set configuration
│   └── experiments/                One YAML file per experiment configuration
│
├── java/src/
│   ├── main/java/za/ac/up/cos790/ Java source code
│   ├── stubs/java/                 HyFlex API stubs (compile fallback without jars)
│   └── test/java/za/ac/up/cos790/ Unit tests (26 tests)
│
├── python/
│   ├── pyproject.toml              Python package metadata and dependencies
│   └── src/xaisphh/                Python analysis package
│       ├── cli.py                  6-stage pipeline CLI entry point
│       ├── io/                     Trace loading and schema validation
│       ├── features/               Feature matrix assembly
│       ├── yates/                  Log returns, percentiles, footrule distance
│       ├── surrogate/              Surrogate model training and evaluation
│       ├── explain/                SHAP and LIME explanation modules
│       └── figures/                Shared matplotlib style
│
├── data/
│   ├── raw/traces/                 Java output: trace CSVs and manifest JSONs
│   └── processed/                  Python output: Parquet files
│
├── results/
│   ├── models/                     Trained surrogate and faithfulness metrics
│   ├── explanations/               SHAP plots, interaction heatmap, LIME figures
│   ├── yates/                      Reference measure tables
│   └── figures/                    Publication PDF figures
│
├── docs/
│   ├── system-explainer.pdf        Plain-English system overview with diagrams
│   ├── trace-schema.md             Trace file column specification (v2)
│   └── design-decisions.md        Design decision log and rationale
│
├── scripts/
│   ├── run_domain.sh               Interactive experiment runner (domain/technique/budget/seed menus)
│   └── test_pipeline.sh            Full end-to-end smoke test
└── docs/
    ├── ProjectAssessment4.pdf      Assessment 4 report (cross-domain results)
    ├── system-explainer.pdf        Plain-English system overview with diagrams
    ├── trace-schema.md             Trace file column specification (v2)
    └── design-decisions.md         Design decision log and rationale
```

---

## Test Results

```
Java:   26 / 26 tests pass    ./gradlew test
Python:  2 /  2 tests pass    python3 -m pytest python/tests/
```

Per-technique surrogate faithfulness (2,500,000 decisions, 6 domains, 4 techniques):

| Technique | Accuracy | ROC-AUC | Majority baseline |
|-----------|----------|---------|------------------|
| SP-CF-LA | 89.3% | 96.8% | 71.5% |
| SP-CF-AILTA | 97.4% | 95.0% | 95.3% |
| SP-SR-LA | 71.7% | 51.8% | 71.8% |
| MP-CF | 99.5% | 96.3% | 99.4% |
