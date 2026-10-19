# Implementation Guide

Complete technical reference for the xai-sphh repository. Covers the research
objective, every component in the codebase, how they connect, and the data that
flows between them.

> **Other docs:** [README.md](README.md) — project overview |
> [RUNNER_INSTRUCTIONS.md](RUNNER_INSTRUCTIONS.md) — how to build and run |
> [docs/system-explainer.pdf](docs/system-explainer.pdf) — plain-English explainer

---

## Table of Contents

1. [Research Objective](#1-research-objective)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Repository Layout](#3-repository-layout)
4. [Java Side — Experiment Runner](#4-java-side--experiment-runner)
   - 4.1 [Entry Point](#41-entry-point)
   - 4.2 [Configuration Loading](#42-configuration-loading)
   - 4.3 [Domain Registry](#43-domain-registry)
   - 4.4 [Budget Policy](#44-budget-policy)
   - 4.5 [Hyper-Heuristic Architecture](#45-hyper-heuristic-architecture)
   - 4.6 [Selection Strategies](#46-selection-strategies)
   - 4.7 [Acceptance Strategies](#47-acceptance-strategies)
   - 4.8 [Search State and Feature Extraction](#48-search-state-and-feature-extraction)
   - 4.9 [Instrumentation — Trace Writing](#49-instrumentation--trace-writing)
   - 4.10 [Run Manifest](#410-run-manifest)
5. [Trace File Format](#5-trace-file-format)
6. [Python Side — Analysis Pipeline](#6-python-side--analysis-pipeline)
   - 6.1 [Package Layout](#61-package-layout)
   - 6.2 [Stage 1: Load (io/loader.py)](#62-stage-1-load-ioloaderpy)
   - 6.3 [Stage 2: Features (features/matrix.py)](#63-stage-2-features-featuresmatrixpy)
   - 6.4 [Stage 3: Yates Measures (yates/)](#64-stage-3-yates-measures-yates)
   - 6.5 [Stage 4: Surrogate Training (surrogate/)](#65-stage-4-surrogate-training-surrogate)
   - 6.6 [Stage 5: Explanations (explain/)](#66-stage-5-explanations-explain)
   - 6.7 [Stage 6: Figures (figures/)](#67-stage-6-figures-figures)
   - 6.8 [CLI Entry Point (cli.py)](#68-cli-entry-point-clipy)
7. [Design Decisions](#7-design-decisions)
8. [Test Suite](#8-test-suite)
9. [Data Flow End-to-End](#9-data-flow-end-to-end)
10. [Configuration Reference](#10-configuration-reference)

---

## 1. Research Objective

The goal of this project is to apply **Explainable AI (XAI)** to understand how
selection perturbative hyper-heuristics (SPHH) make decisions across multiple
problem domains.

A hyper-heuristic sits above a set of low-level heuristics (LLHs) and decides,
at each step, which LLH to apply and whether to keep the resulting solution. By
instrumenting every decision with a state snapshot, we build a rich dataset of
(state, decision) pairs. A surrogate ML model is then trained on this data and
explained using SHAP and LIME to reveal what features drive acceptance behaviour.

The key research question is: **what does the hyper-heuristic implicitly learn
to respond to, and does this differ between single-point and population-based
search?**

---

## 2. High-Level Architecture

```
 YAML config
     │
     ▼
 Java Experiment Runner
     │
     │  HyFlex problem domain (SAT, BinPacking, FlowShop, TSP, VRP, PS)
     │  Selection strategy  (Choice Function | Simple Random)
     │  Acceptance strategy (Late Acceptance | AILTA | SA | IOE | Naive)
     │  OR Multi-point search with population replacement
     │
     │  Every iteration → SearchState snapshot → FeatureExtractor
     │                                          │
     ▼                                          ▼
 trace_<name>_<domain>_<inst>_<seed>.csv     feat_* columns
 manifest_<name>_<domain>_<inst>_<seed>.json
     │
     ▼
 Python Analysis Pipeline (8 stages)
     │
     ├─ load      → data/interim/traces.parquet + run_metadata.parquet
     ├─ features  → data/processed/X.parquet, y.parquet, technique.parquet
     ├─ yates     → log_returns, percentile_ranks, footrule_distances, acceptance_rate
     ├─ train     → results/models/<technique>/surrogate.joblib + faithfulness_metrics.json
     ├─ explain   → results/explanations/<technique>/SHAP + LIME grid outputs
     ├─ figures   → convergence.pdf, per-technique shap_importance.pdf
     ├─ stats     → Wilcoxon pairwise significance tests (CSV)
     └─ report    → results/report.pdf (multi-page PDF of all outputs)
```

---

## 3. Repository Layout

```
xai-sphh/
├── build.gradle                        Gradle build: deps, sourceSets, jar config
├── settings.gradle                     Project name
├── gradlew / gradlew.bat               Gradle wrapper (no local Gradle needed)
│
├── lib/hyflex/
│   ├── chesc-fixed-no-ps.jar           HyFlex CHeSC domains: SAT, BinPacking, FlowShop, TSP, VRP
│   └── chesc-ps.jar                    HyFlex CHeSC domain: PersonnelScheduling
│
├── config/
│   ├── features.yaml                   Feature set configuration (names, enable/disable)
│   └── experiments/
│       ├── baseline.yaml               SP-SR-LA (baseline)
│       ├── sp-cf-la.yaml               SP-CF-LA
│       ├── sp-cf-ailta.yaml            SP-CF-AILTA
│       └── mp-cf.yaml                  MP-CF (population search)
│
├── java/src/
│   ├── main/java/za/ac/up/cos790/
│   │   ├── Main.java                   Entry point: reads config, calls ExperimentRunner
│   │   ├── acceptance/                 Acceptance strategy implementations
│   │   │   ├── AcceptanceStrategy.java (interface, in hyperheuristic/)
│   │   │   ├── LateAcceptance.java
│   │   │   ├── AILTA.java
│   │   │   ├── SimulatedAnnealing.java
│   │   │   ├── ImprovingOrEqual.java
│   │   │   └── NaiveAcceptance.java
│   │   ├── selection/                  Selection strategy implementations
│   │   │   ├── ChoiceFunction.java
│   │   │   ├── ChoiceFunctionTerms.java
│   │   │   └── SimpleRandom.java
│   │   ├── hyperheuristic/             Core hyper-heuristic framework
│   │   │   ├── SelectionStrategy.java  (interface)
│   │   │   ├── AcceptanceStrategy.java (interface)
│   │   │   ├── HyperHeuristicBase.java (abstract, single-point loop)
│   │   │   ├── singlepoint/
│   │   │   │   └── SinglePointHyperHeuristic.java
│   │   │   └── multipoint/
│   │   │       └── MultiPointHyperHeuristic.java
│   │   ├── state/
│   │   │   ├── SearchState.java        Immutable snapshot of the search state
│   │   │   └── FeatureExtractor.java   Converts SearchState to feat_* double map
│   │   ├── instrumentation/
│   │   │   ├── TraceRecord.java        One row of the trace CSV (Java record)
│   │   │   ├── TraceWriter.java        Interface for writing trace records
│   │   │   ├── CsvTraceWriter.java     CSV implementation of TraceWriter
│   │   │   ├── RunManifest.java        Run metadata written to JSON
│   │   │   └── ScoreVector.java        Selector score snapshot per iteration
│   │   ├── experiment/
│   │   │   ├── ExperimentRunner.java   Wires config → domain → HH → run → manifest
│   │   │   ├── BudgetPolicy.java       Iteration-based or time-based stopping
│   │   │   └── SeedPolicy.java         Seed management utilities
│   │   ├── config/
│   │   │   ├── RunConfig.java          Parsed YAML config (Java record)
│   │   │   └── ConfigLoader.java       YAML → RunConfig via SnakeYAML
│   │   └── domain/
│   │       ├── DomainRegistry.java     Maps domain name strings to constructors
│   │       └── HeuristicCatalogue.java Queries heuristic types from a domain
│   ├── stubs/java/AbstractClasses/     HyFlex API stubs (used when jars absent)
│   │   ├── HyperHeuristic.java
│   │   └── ProblemDomain.java
│   └── test/java/za/ac/up/cos790/
│       ├── AcceptanceStrategyTest.java
│       ├── ChoiceFunctionTest.java
│       ├── DomainBarrierTest.java
│       ├── FeatureExtractorTest.java
│       ├── MultiPointHyperHeuristicTest.java
│       └── TraceSchemaTest.java
│
├── python/
│   ├── pyproject.toml                  Package metadata, dependencies, entry point
│   └── src/xaisphh/
│       ├── cli.py                      Click CLI: 8 commands (load/features/yates/train/explain/figures/stats/report)
│       ├── io/
│       │   ├── schema.py               Column names, dtypes, prefixes, schema version
│       │   └── loader.py               CSV → DataFrame + schema validation + manifest loading
│       ├── features/
│       │   └── matrix.py               DataFrame → (X, y, technique) feature matrix
│       ├── yates/
│       │   ├── log_returns.py          Log return computation with clipping + heuristic stats
│       │   ├── percentiles.py          Percentile rank and bucket helpers
│       │   ├── footrule.py             Spearman footrule distance between heuristic rankings
│       │   └── acceptance_rate.py      Acceptance/improvement rate vs. search progress
│       ├── surrogate/
│       │   ├── train.py                Train GradientBoosting / RF / LR surrogate (per-technique)
│       │   ├── evaluate.py             5-fold CV faithfulness metrics
│       │   └── ablation.py             Identity/class ablation study
│       ├── explain/
│       │   ├── shap_global.py          SHAP TreeExplainer / KernelExplainer, summary plot
│       │   ├── shap_interactions.py    SHAP interaction values, heatmap
│       │   ├── lime_local.py           LIME LimeTabularExplainer, single-instance figure
│       │   └── lime_grid.py            Systematic LIME grid over evenly-spaced decision points
│       ├── figures/
│       │   └── style.py                Shared matplotlib style, colour palette
│       ├── report/
│       │   └── generate.py             Multi-page PDF report generator
│       └── scripts/
│           ├── generate_configs.py     Batch config generation helper
│           ├── run_matrix.py           Programmatic experiment matrix runner
│           └── wilcoxon_stats.py       Pairwise Wilcoxon signed-rank tests with Holm correction
│
├── data/
│   ├── raw/traces/                     Java output: trace CSVs + manifest JSONs
│   ├── interim/                        Stage 1 output: traces.parquet, run_metadata.parquet
│   └── processed/                      Stage 2 output: X.parquet, y.parquet, technique.parquet
│
├── results/
│   ├── models/
│   │   ├── <technique>/                Per-technique: surrogate.joblib, faithfulness_metrics.json
│   │   └── technique_comparison.csv    Cross-technique faithfulness summary
│   ├── explanations/
│   │   ├── <technique>/                Per-technique: SHAP CSVs, PDF plots, LIME grid outputs
│   │   └── shap_comparison_by_technique.csv  Cross-technique SHAP comparison
│   ├── yates/                          log_returns, percentile_ranks, footrule_distances CSVs
│   ├── figures/                        convergence.pdf, shap_importance_<technique>.pdf
│   └── report.pdf                      Generated PDF report
│
├── docs/
│   ├── trace-schema.md                 Authoritative column specification (v2)
│   ├── design-decisions.md             Resolved design decisions (DD-01 through DD-28)
│   └── ProjectAssessment4.pdf          Assessment 4 report
│
├── scripts/
│   ├── run_domain.sh                   Interactive experiment runner (domain/technique/budget/seed menus)
│   └── test_pipeline.sh                Full end-to-end smoke test
│
├── README.md
├── RUNNER_INSTRUCTIONS.md              Step-by-step build and run guide
└── IMPLEMENTATION_GUIDE.md            This file
```

---

## 4. Java Side — Experiment Runner

### 4.1 Entry Point

**File:** `java/src/main/java/za/ac/up/cos790/Main.java`

The application receives exactly one command-line argument: the path to a YAML
config file. It delegates entirely to `ExperimentRunner`.

```
args[0] → ConfigLoader.load() → RunConfig → ExperimentRunner.run()
```

### 4.2 Configuration Loading

**Files:** `config/ConfigLoader.java`, `config/RunConfig.java`

`ConfigLoader` uses SnakeYAML to parse the YAML file into a `RunConfig` Java
record. `RunConfig` holds:

| Field | Type | Purpose |
|-------|------|---------|
| `techniqueName` | String | Parsed to determine mode/selector/acceptor |
| `domain` | String | Looked up in `DomainRegistry` |
| `instanceIndex` | int | Which of the 10 domain instances to load |
| `seed` | long | Random seed for reproducibility |
| `budgetType` | String | `"iterations"` or `"time"` |
| `budgetValue` | long | Number of iterations or milliseconds |
| `outputDirectory` | Path | Where to write trace CSV and manifest JSON |
| `techniqueParameters` | Map<String,String> | Optional extras (listLength, populationSize, etc.) |

### 4.3 Domain Registry

**File:** `domain/DomainRegistry.java`

Maps domain name strings to `DomainEntry` records that contain a factory
`Supplier<ProblemDomain>` and the list of valid instance indices.

| Domain name | Class | Jar |
|-------------|-------|-----|
| `SAT` | `SAT.SAT` | chesc-fixed-no-ps.jar |
| `BinPacking` | `BinPacking.BinPacking` | chesc-fixed-no-ps.jar |
| `FlowShop` | `FlowShop.FlowShop` | chesc-fixed-no-ps.jar |
| `TSP` | `travelingSalesmanProblem.TSP` | chesc-fixed-no-ps.jar |
| `VRP` | `VRP.VRP` | chesc-fixed-no-ps.jar |
| `PersonnelScheduling` | `PersonnelScheduling.PersonnelScheduling` | chesc-ps.jar |

Each domain constructor receives a `long` seed (using `System.nanoTime()` so
that independent runs are not synchronised even with the same config seed).

### 4.4 Budget Policy

**File:** `experiment/BudgetPolicy.java`

Controls when the search loop terminates and computes normalised progress (0.0
to 1.0) used in feature extraction.

- **Iteration-based**: loop runs for exactly `budgetValue` heuristic applications.
- **Time-based**: loop runs until `budgetValue` milliseconds have elapsed.

`BudgetPolicy` is separate from the HyFlex `setTimeLimit` / `hasTimeExpired`
mechanism. HyFlex's timer is set to a generous wall-clock cap (default 1 hour)
for iteration-based budgets so that the framework's own timer never interferes.
`BudgetPolicy.isExhausted()` is the primary termination condition.

### 4.5 Hyper-Heuristic Architecture

The HyFlex framework requires all hyper-heuristics to extend
`AbstractClasses.HyperHeuristic`. The HyFlex protocol is:

```
hh.setTimeLimit(ms);       // must be called first
hh.loadProblemDomain(pd);  // stores the domain, then calls solve()
hh.run();                  // outer framework method that invokes solve()
```

This project uses three classes:

#### HyperHeuristicBase (abstract, single-point)

**File:** `hyperheuristic/HyperHeuristicBase.java`

Implements the entire single-point search loop inside `solve(ProblemDomain)`.
Subclasses provide the selection strategy, acceptance strategy, and
depth-of-search / intensity-of-mutation values by implementing four abstract
methods.

**Solution memory layout:**
- Slot 0 (`INCUMBENT_SLOT`): current working solution
- Slot 1 (`CANDIDATE_SLOT`): candidate produced each iteration
- Slot 2 (`BEST_SO_FAR_SLOT`): best solution found across the whole run

**Loop body (per iteration):**
1. Build `SearchState` snapshot from counters, windows and extrema
2. Call `selector.select(state)` → heuristic index
3. Set depth-of-search and intensity-of-mutation via `problem.setDepthOfSearch()` and `problem.setIntensityOfMutation()`
4. Apply heuristic: `problem.applyHeuristic(hId, INCUMBENT_SLOT, CANDIDATE_SLOT)`
5. Update `bestSoFar` from candidate (before acceptance decision)
6. Update running min/max
7. Ask `acceptor.accept(incumbent, candidate, bestSoFar, iteration)` → boolean
8. If accepted: copy candidate to incumbent slot, update incumbent objective
9. Call `selector.recordOutcome(hId, delta, cpuTimeMs)`
10. Extract features via `FeatureExtractor.extract(state)`
11. Write `TraceRecord` to CSV
12. Advance sliding windows

At end of run: copy best-so-far slot back to incumbent slot so HyFlex scores
the best found result.

#### SinglePointHyperHeuristic

**File:** `hyperheuristic/singlepoint/SinglePointHyperHeuristic.java`

Concrete subclass of `HyperHeuristicBase`. Holds a `SelectionStrategy` and an
`AcceptanceStrategy` and returns them from the abstract methods. Depth-of-search
and intensity-of-mutation are fixed at 0.1 (the HyFlex-documented default).

#### MultiPointHyperHeuristic

**File:** `hyperheuristic/multipoint/MultiPointHyperHeuristic.java`

A population-based hyper-heuristic that does **not** use an `AcceptanceStrategy`.
Replacement is the acceptance mechanism.

**Solution memory layout:**
- Slots `0..popSize-1`: population individuals
- Slot `popSize`: candidate produced each iteration

**Population protocol:**
- **Target selection**: binary tournament — draw two distinct individuals, pick
  the worse one (higher objective) to maximise replacement benefit.
- **Second parent**: binary tournament excluding the target index, for crossover
  heuristics.
- **Replacement rule**: replace target only when candidate is strictly better
  AND the target is not the population-best slot (elitism guard).
- **Selector**: shared globally across the population (not per-individual).

### 4.6 Selection Strategies

Both implement the `SelectionStrategy` interface:

```java
int select(SearchState state);
void recordOutcome(int heuristicId, double delta, double cpuTimeMs);
ScoreVector scoreVector();
```

#### SimpleRandom

**File:** `selection/SimpleRandom.java`

Selects uniformly at random. Ignores `recordOutcome`. `scoreVector()` returns a
vector of NaN (no meaningful scores).

#### ChoiceFunction

**File:** `selection/ChoiceFunction.java`

Modified Choice Function (Cowling, Kendall & Soubeiga 2001; adaptive weighting
after Tyasnurita, Ozcan & John 2017).

**Score formula:**
```
CF(h) = φ·f1[h] + φ·f2[lastH][h] + (1−φ)·f3[h]
```

- `f1[h]` — accumulated normalised reward from applying h alone (exponential decay)
- `f2[i][j]` — accumulated reward from applying j immediately after i (asymmetric matrix)
- `f3[h]` — elapsed CPU time since h was last applied (promotes idle heuristics)
- `φ` — adaptive weight: snaps to 0.99 on improvement, decays by 0.01 per
  non-improving step (floor 0.01)

**Warm-up:** each heuristic is applied exactly once in index order before scoring
begins, giving `f1` at least one observation per heuristic.

Selection: `argmax CF(h)` with random tie-breaking.

### 4.7 Acceptance Strategies

All implement the `AcceptanceStrategy` interface:

```java
boolean accept(double incumbent, double candidate, double bestSoFar, long iteration);
```

| Class | Location | Behaviour |
|-------|----------|-----------|
| `LateAcceptance` | `acceptance/LateAcceptance.java` | Accept if candidate ≤ incumbent OR candidate ≤ history[L iterations ago]. List length L=50 (default). |
| `AILTA` | `acceptance/AILTA.java` | Adaptive ILTA — decaying threshold calibrated from the initial objective. |
| `SimulatedAnnealing` | `acceptance/SimulatedAnnealing.java` | Probabilistic acceptance via Boltzmann criterion; geometric temperature decay. |
| `ImprovingOrEqual` | `acceptance/ImprovingOrEqual.java` | Accept only if candidate ≤ incumbent. |
| `NaiveAcceptance` | `acceptance/NaiveAcceptance.java` | Always accept. |

### 4.8 Search State and Feature Extraction

#### SearchState

**File:** `state/SearchState.java`

An immutable Java record that snapshots everything the hyper-heuristic is
legally allowed to observe at a single decision point. The **domain barrier
rule** applies: no field may encode problem-specific information (variable
assignments, graph topology, schedule slots, etc.). All values derive from
objective values, iteration counts, heuristic indices/classes only.

Key fields:

| Field | Description |
|-------|-------------|
| `heuristicCount` | Total low-level heuristics available |
| `iterationIndex` | Zero-based iteration counter |
| `budgetProgress` | Normalised progress [0.0, 1.0] |
| `currentObjective` | Incumbent objective value |
| `bestSoFar` | Best objective seen so far |
| `iterationsSinceImprovement` | Steps since best improved |
| `iterationsSinceAccept` | Steps since last accepted move |
| `runningMin / runningMax` | Observed objective extrema (not full-run — no future leak) |
| `recentDeltas` | Last 50 objective deltas (newest first) |
| `recentLogReturns` | Last 50 log returns (newest first, NaN for non-positive) |
| `lastHeuristics` | Last 3 heuristic indices (newest first, -1 if absent) |
| `lastHeuristicClasses` | Last 3 heuristic type ordinals (newest first, -1 if absent) |
| `populationBest/Mean/Diversity` | Population statistics (NaN for single-point) |
| `populationTargetRank` | Rank of target in population (-1 for single-point) |

#### FeatureExtractor

**File:** `state/FeatureExtractor.java`

Converts a `SearchState` into an ordered `LinkedHashMap<String, Double>` of
named features. Each key is a bare name (without `feat_` prefix); the prefix is
added by `CsvTraceWriter`.

The 16 features (Decision 28):

| Feature name | Description |
|---|---|
| `llh_count` | Number of LLHs available |
| `progress` | Budget fraction consumed |
| `obj_norm` | Current objective normalised by running range |
| `gap_to_best` | (current − best) / running range |
| `iters_since_improve` | Steps since best improved |
| `improve_rate_50` | Fraction of last 50 steps that improved |
| `mean_logret_50` | Mean log return over last 50 steps |
| `last_h1/h2/h3` | Last 3 heuristic indices (categorical, sentinel -1) |
| `last_class1/class2/class3` | Last 3 heuristic type ordinals (categorical, sentinel -1) |
| `iters_since_accept` | Steps since last accepted move |
| `pop_diversity` | Population coefficient of variation (NaN for single-point) |
| `pop_target_rank` | Rank of target in population (-1 for single-point) |

### 4.9 Instrumentation — Trace Writing

**Files:** `instrumentation/TraceRecord.java`, `instrumentation/CsvTraceWriter.java`,
`instrumentation/TraceWriter.java`

`CsvTraceWriter` implements `TraceWriter` (and `AutoCloseable`). It opens a
`BufferedWriter` on construction and writes the CSV header from
`TraceRecord.FIXED_COLUMNS` + dynamic feature/score column names from the first
record.

Special handling:
- `logReturn` that is `NaN` or infinite is written as an **empty CSV field**
  (not the string `"NaN"`), so that pandas loads it as `float64 NaN` rather
  than a string (design decision DD-08).
- `accepted` is written as `true` / `false`.
- `score_*` columns use heuristic index as the key suffix.

### 4.10 Run Manifest

**File:** `instrumentation/RunManifest.java`

After each run, a JSON file is written alongside the trace CSV:

```json
{
  "stem": "SP-CF-LA_SAT_0_42",
  "techniqueName": "SP-CF-LA",
  "domain": "SAT",
  "instanceIndex": 0,
  "seed": 42,
  "gitCommit": "<sha>",
  "hyflexVersion": "<version>",
  "startTime": "...",
  "endTime": "...",
  "machineId": "...",
  "finalObjective": 12.0
}
```

The manifest records the exact code version and machine so results can be
reproduced and attributed.

---

## 5. Trace File Format

**Spec:** `docs/trace-schema.md`
**Schema version:** 2

Each trace CSV has one row per heuristic application. Column order:

**Fixed columns (19):**

| Column | Type | Notes |
|--------|------|-------|
| `run_id` | string | UUID identifying the run |
| `iteration` | int64 | 0-based counter |
| `heuristic_id` | int32 | LLH index |
| `heuristic_class` | string | `MUTATION`, `RUIN_RECREATE`, `LOCAL_SEARCH`, `CROSSOVER` |
| `depth_of_search` | float64 | Fixed at 0.1 in current implementation |
| `intensity_of_mutation` | float64 | Fixed at 0.1 in current implementation |
| `target_index` | int32 | Memory slot targeted (0 for single-point) |
| `source_index` | int32 | Primary source slot |
| `second_parent_index` | int32 | Second parent slot for crossover, or -1 |
| `objective_before` | float64 | Incumbent/target objective before application |
| `objective_after` | float64 | Candidate objective after application |
| `delta` | float64 | `objective_after − objective_before` |
| `log_return` | float64 | `log(after/before)` or empty for non-positive |
| `accepted` | bool | Whether candidate was kept |
| `best_so_far` | float64 | Best objective seen up to this iteration |
| `cpu_time_ms` | float64 | Wall-clock ms for heuristic application only |
| `pop_best` | float64 | Population best (= best_so_far for single-point) |
| `pop_mean` | float64 | Population mean (= objective_before for single-point) |
| `pop_diversity` | float64 | Population CoV (0.0 for single-point; NaN when mean=0) |

**Dynamic columns (variable):**
- `feat_*` — 16 state features (see FeatureExtractor above)
- `score_*` — per-heuristic selector scores (`score_0`, `score_1`, ...; NaN for SimpleRandom)

Typical row count: 100,000 (one per iteration for a 100k-iteration run).
Typical file size: 20–42 MB.

---

## 6. Python Side — Analysis Pipeline

### 6.1 Package Layout

The Python package is installed in editable mode (`pip install -e python/`).
The entry point `xaisphh` maps to `xaisphh.cli:main`.

```
python/src/xaisphh/
├── cli.py             All 8 CLI subcommands (Click)
├── io/
│   ├── schema.py      FIXED_COLUMNS, FIXED_DTYPES, FEAT_PREFIX, SCORE_PREFIX
│   └── loader.py      load_traces(), load_manifests_for_traces(), build_run_metadata()
├── features/
│   └── matrix.py      build_feature_matrix()
├── yates/
│   ├── log_returns.py compute_log_returns(), heuristic_stats()
│   ├── percentiles.py percentile_rank(), bucket_objectives()
│   ├── footrule.py    heuristic_ranking(), footrule_distance()
│   └── acceptance_rate.py  acceptance_rate_by_progress(), save_acceptance_rate_plot()
├── surrogate/
│   ├── train.py       train_surrogate(), save_surrogate(), load_surrogate(), drop_constant_features()
│   ├── evaluate.py    faithfulness_score()
│   └── ablation.py    run_ablation()
├── explain/
│   ├── shap_global.py       compute_shap_values(), global_feature_importance(), save_summary_plot()
│   ├── shap_interactions.py compute_interaction_values(), save_interaction_heatmap()
│   ├── lime_local.py        explain_instance(), save_explanation_plot()
│   └── lime_grid.py         lime_grid(), condition_frequency_table(), save_condition_frequency_plot()
├── figures/
│   └── style.py       apply_style(), domain_colour(), COLOURS
├── report/
│   └── generate.py    generate_report()
└── scripts/
    ├── generate_configs.py  Batch YAML config generation
    ├── run_matrix.py        Programmatic full-matrix runner
    └── wilcoxon_stats.py    wilcoxon_pairwise() with Holm correction
```

### 6.2 Stage 1: Load (`io/loader.py`)

**What it does:** Reads every CSV trace file from a directory, validates the
schema, casts dtypes, and concatenates into a single Parquet file.

**Key function:** `load_traces(directory, pattern="*.csv") → pd.DataFrame`

Schema validation steps:
1. Check all 19 fixed columns are present in every file
2. Cast each column to its declared dtype (see `io/schema.py: FIXED_DTYPES`)
3. `log_return` empty fields → `NaN` float64 (handled by `pd.to_numeric(..., errors="coerce")`)
4. `accepted` string `"true"/"false"` → pandas `boolean` dtype
5. Dynamic `feat_*` and `score_*` columns cast to `float64`

**Output:** `data/interim/traces.parquet` — a single Parquet file containing
all runs concatenated, schema-validated. Also `data/interim/run_metadata.parquet`
containing per-run attributes (technique, domain, seed, stub flag, finalObjective).

**Schema constants** (`io/schema.py`):
- `FIXED_COLUMNS` — ordered list of the 19 column names
- `FIXED_DTYPES` — dict mapping each column to its dtype string
- `FEAT_PREFIX = "feat_"` — prefix used to identify feature columns
- `SCORE_PREFIX = "score_"` — prefix used to identify selector score columns
- `SCHEMA_VERSION = 2`

### 6.3 Stage 2: Features (`features/matrix.py`)

**What it does:** Selects the `feat_*` columns as the predictor matrix X and
the `accepted` column as the binary target y.

**Key function:** `build_feature_matrix(df, drop_score_columns=True) → (X, y)`

Critical design decisions:
- **NaN fill with -1.0**: `feat_pop_diversity` and `feat_pop_target_rank` are
  NaN for single-point runs. Rather than dropping those rows (which would
  eliminate all single-point data), NaN is filled with -1.0 — the project-wide
  sentinel for "not applicable". This is consistent with the -1 sentinel used
  by `FeatureExtractor` for absent heuristic history entries.
- `y = df["accepted"].astype(int)` — converts boolean to 0/1 integer.

**Output:** `data/processed/X.parquet` (feature matrix), `data/processed/y.parquet`
(target), `data/processed/technique.parquet` (per-row technique label used by
`train` and `explain` to split data per technique).

Typical shape: `(2500000, 16)` for 25 runs × 100k iterations.

### 6.4 Stage 3: Yates Measures (`yates/`)

Three reference measures adapted from Yates et al.:

#### Log Returns (`yates/log_returns.py`)

```python
compute_log_returns(df) → pd.Series
```

Computes `log(objective_after / objective_before)` for each row. Returns NaN
for rows where either value is non-positive. Grouped by `heuristic_id` to
produce a summary table of mean/std/quantiles per LLH.

#### Percentile Ranks (`yates/percentiles.py`)

```python
percentile_rank(series) → pd.Series          # series.rank(pct=True)
bucket_objectives(df, n_buckets=10) → pd.Series  # pd.qcut into decile buckets
```

Ranks each `objective_after` value within the run to see which LLHs consistently
produce better solutions.

#### Footrule Distance (`yates/footrule.py`)

```python
heuristic_ranking(df) → pd.Series   # heuristic_id ranked by mean log_return
footrule_distance(rank_a, rank_b) → float   # Spearman footrule (L1 rank distance)
```

Compares heuristic rankings in the first half of the run versus the second half.
A high footrule distance indicates the search learned to prefer different LLHs
over time (adaptive behaviour).

### 6.5 Stage 4: Surrogate Training (`surrogate/`)

#### Training (`surrogate/train.py`)

```python
train_surrogate(X, y, model_type="gradient_boosting", random_state=42) → model
drop_constant_features(X) → (X_filtered, dropped_list)
```

By default the `train` CLI command trains **one surrogate per technique**, not
a pooled model. Constant features (e.g. `feat_pop_diversity` for single-point
techniques where it is always -1.0) are automatically dropped before training.
Three model families are supported:

| Model | Config | Notes |
|-------|--------|-------|
| `gradient_boosting` | 200 trees, depth 4, lr 0.05, subsample 0.8 | Default. SHAP TreeExplainer compatible. |
| `random_forest` | 200 trees, no depth limit, min_leaf 5 | Faster. Also SHAP-compatible. |
| `logistic_regression` | Pipeline: StandardScaler + LR (C=1.0) | Interpretable baseline. Needs KernelExplainer. |

Each technique's model is serialised with `joblib` to
`results/models/<technique>/surrogate.joblib`.

#### Faithfulness (`surrogate/evaluate.py`)

```python
faithfulness_score(model, X, y) → dict
```

5-fold stratified cross-validation. Returns:

| Metric | Meaning |
|--------|---------|
| `accuracy` ± `accuracy_std` | Fraction of decisions correctly predicted |
| `roc_auc` ± `roc_auc_std` | Area under the ROC curve |
| `f1` ± `f1_std` | Harmonic mean of precision and recall |
| `majority_baseline_accuracy` | `max(class_freq)` — trivial classifier baseline |

A surrogate with ROC-AUC well above 0.5 is a faithful approximation of the
real policy, making SHAP explanations valid. SP-SR-LA is a known exception:
Simple Random selection creates no learnable correlations, so its surrogate
degrades to random (ROC-AUC ≈ 0.52).

**Observed results** (25 runs, 6 domains, 100k iterations each):

| Technique | Accuracy | ROC-AUC | Majority baseline |
|-----------|----------|---------|------------------|
| SP-CF-LA | 89.3% | 96.8% | 71.5% |
| SP-CF-AILTA | 97.4% | 95.0% | 95.3% |
| SP-SR-LA | 71.7% | 51.8% | 71.8% ← random |
| MP-CF | 99.5% | 96.3% | 99.4% |

#### Ablation (`surrogate/ablation.py`)

```python
run_ablation(X, y, model_type, random_state) → pd.DataFrame
```

Trains three additional model variants per technique: full features, features
excluding heuristic identity (`last_h*`), and features excluding heuristic
class (`last_class*`). Compares faithfulness to reveal the contribution of
categorical identity vs. functional class information.


**Observed result:** 88.5% accuracy vs 57.5% baseline, ROC-AUC 95.3%.

### 6.6 Stage 5: Explanations (`explain/`)

#### Global SHAP (`explain/shap_global.py`)

```python
compute_shap_values(model, X) → np.ndarray   # shape (n_samples, n_features)
global_feature_importance(shap_values, feature_names) → pd.DataFrame
save_summary_plot(shap_values, X, output_path)
```

For tree-based models: `shap.TreeExplainer` (exact, fast).
For logistic regression: `shap.KernelExplainer` with k-means summarised
background (100 representatives) — approximate but model-agnostic.

`global_feature_importance` returns a DataFrame sorted by `mean |SHAP value|`,
which measures each feature's average contribution to the prediction (regardless
of direction).

The **beeswarm summary plot** shows each instance as a dot: x-axis = SHAP value,
colour = feature value, sorted by mean |SHAP|.

#### SHAP Interactions (`explain/shap_interactions.py`)

```python
compute_interaction_values(model, X) → np.ndarray  # shape (n, n_features, n_features)
save_interaction_heatmap(interaction_values, feature_names, output_path)
```

Only available for tree-based models. Computes pairwise interaction effects:
`shap_interaction[i,j]` measures how feature i and feature j jointly influence
the prediction beyond their individual effects. The heatmap shows
`mean |interaction value|` — diagonal is main effects, off-diagonal is pairwise
interactions.

**Performance note:** interaction computation scales as O(n × features²). For
400k samples this is prohibitively slow; the CLI subsamples to 2,000 rows by
default (`--n-interactions 2000`).

#### LIME Grid (`explain/lime_grid.py`)

```python
lime_grid(model, X, progress, n_grid=50, seed=42) → pd.DataFrame
condition_frequency_table(grid_df) → pd.DataFrame
save_condition_frequency_plot(freq_df, output_path)
```

Rather than explaining arbitrary instances, the LIME grid selects `n_grid`
decision points evenly distributed across the search progress dimension
(0.0 → 1.0). This gives a systematic view of how the local decision policy
evolves from early to late search. `condition_frequency_table` aggregates the
most common LIME conditions across all grid points, showing which feature
thresholds recur most often.

**Note:** Under severe class imbalance the local neighbourhood is dominated by
the majority class and LIME weights approach zero. This affects single-point
techniques with >95% acceptance rate. Check `lime_condition_frequency.csv`
to confirm conditions are present before interpreting results.

#### LIME Local (`explain/lime_local.py`)

```python
explain_instance(model, X, instance_index, num_features=10, num_samples=5000) → Explanation
save_explanation_plot(explanation, output_path)
```

`LimeTabularExplainer` fits a local linear model around a single decision
(instance) by generating `num_samples` perturbed versions of that instance,
predicting each, and fitting a weighted linear regression. Used for one-off
instance-level inspection; the LIME grid (above) is preferred for systematic
analysis.

### 6.7 Stage 6: Figures (`figures/`)

**File:** `figures/style.py`

Applies a shared matplotlib style (Times font, figure width matching LaTeX
\textwidth, consistent colour palette) to all plots. All figure functions call
`apply_style()` before creating axes.

Two figures produced by the `figures` CLI command:
- `convergence.pdf` — best-so-far over iteration, one line per run
- `shap_importance.pdf` — horizontal bar chart of mean |SHAP| per feature

### 6.8 CLI Entry Point (`cli.py`)

All eight pipeline stages are exposed as Click subcommands under the `xaisphh`
group. Each command is fully self-contained: it imports only what it needs
(lazy imports to keep startup fast) and reads/writes files from the declared
`--in` and `--out` paths.

Invoked as:
```bash
python3 -m xaisphh.cli <command> [options]
# or after pip install -e python/:
xaisphh <command> [options]
```

---

## 7. Design Decisions

Key decisions recorded in `docs/design-decisions.md`:

| Decision | What was decided |
|----------|-----------------|
| DD-01 | Selection algorithm: Choice Function (primary) vs Simple Random (baseline) |
| DD-02 | Acceptance parameters: LA list length L=50, SA initial temp 1000 |
| DD-03 | Feature set: 16 domain-agnostic features (see FeatureExtractor) |
| DD-04 | Budget: iteration-based (100k) for reproducibility |
| DD-05 | Surrogate family: GradientBoosting (default), RF, LR as alternatives |
| DD-06 | XAI scope: global SHAP (population-level) + LIME local (individual decisions) |
| DD-07 | Choice Function f2 update: asymmetric pair matrix (f2[i][j] ≠ f2[j][i]) |
| DD-08 | Log return for non-positive objectives: empty CSV field (not string NaN) |
| DD-22 | Multi-point protocol: shared selector, binary tournament, elitism guard |
| DD-24 | CPU time measurement: around `applyHeuristic` only, not logging overhead |
| DD-25 | MP has no AcceptanceStrategy — replacement rule is the acceptance mechanism |
| DD-28 | Normalisation: running extrema only (full-run range leaks future information) |

---

## 8. Test Suite

### Java Tests (26 tests, `java/src/test/java/`)

| Test class | What it tests |
|---|---|
| `AcceptanceStrategyTest` | LateAcceptance, AILTA, SA, IOE, Naive correctness |
| `ChoiceFunctionTest` | CF score formula, phi update, warm-up, tie-breaking |
| `DomainBarrierTest` | FeatureExtractor feature names contain no domain-specific terms |
| `FeatureExtractorTest` | Feature values for known SearchState inputs |
| `MultiPointHyperHeuristicTest` | Elitism, one-record-per-application, constructor contract |
| `TraceSchemaTest` | TraceRecord.FIXED_COLUMNS matches docs/trace-schema.md |

Run with: `./gradlew test`

### Python Tests (2 tests, `python/tests/`)

| Test file | What it tests |
|---|---|
| `test_schema.py` | FIXED_COLUMNS in schema.py matches docs/trace-schema.md; FIXED_DTYPES covers every column |

Run with: `python3 -m pytest python/tests/`

### HyFlex Stubs

When the real HyFlex jars are absent from `lib/hyflex/`, Gradle automatically
adds `java/src/stubs/java/` to the source set. The stubs define the
`AbstractClasses.HyperHeuristic` and `AbstractClasses.ProblemDomain` abstract
classes with the same API as the real jars, so the project compiles and all
non-HyFlex unit tests can run without the proprietary jars.

---

## 9. Data Flow End-to-End

```
YAML config file
    │
    ▼
ConfigLoader.load()
    → RunConfig record
    │
    ▼
ExperimentRunner.run()
    → DomainRegistry.get(domain)  → ProblemDomain instance
    → Build selector (CF or SR)
    → Build acceptor (LA / AILTA / SA / IOE / Naive)
    → Build HH (SinglePoint or MultiPoint)
    → hh.setTimeLimit() → hh.loadProblemDomain() → hh.run()
    │
    Inside solve():
        per-iteration:
            SearchState snapshot
                → FeatureExtractor.extract() → feat_* map
                → selector.scoreVector()     → score_* map
            → TraceRecord
            → CsvTraceWriter.write()         → one CSV row
    │
    ▼
data/raw/traces/
    trace_<technique>_<domain>_<inst>_<seed>.csv   (100k rows, ~35 columns)
    manifest_<technique>_<domain>_<inst>_<seed>.json
    │
    ▼  python3 -m xaisphh.cli load
load_traces()
    → validate_schema()
    → cast dtypes
    → pd.concat()
build_run_metadata()   → technique, domain, seed, stub flag per run
    ▼
data/interim/traces.parquet      (all runs combined)
data/interim/run_metadata.parquet
    │
    ▼  python3 -m xaisphh.cli features
build_feature_matrix()
    → select feat_* columns → X (fill NaN → -1.0)
    → df["accepted"].astype(int) → y
    → technique label per row
    ▼
data/processed/X.parquet          shape (N, 16)
data/processed/y.parquet          shape (N,)
data/processed/technique.parquet  shape (N,)
    │
    ├──▶  python3 -m xaisphh.cli yates
    │         compute_log_returns() with clipping
    │         heuristic_stats()             → mean/median/IQR/trimmed per LLH
    │         percentile_rank(), bucket_objectives()
    │         heuristic_ranking(), footrule_distance()
    │         acceptance_rate_by_progress()
    │         ▼
    │     results/yates/log_returns_by_heuristic.csv
    │     results/yates/percentile_ranks.csv
    │     results/yates/footrule_distances.csv
    │     results/yates/acceptance_rate_by_progress.csv
    │
    ▼  python3 -m xaisphh.cli train [--ablation]
for each technique:
    drop_constant_features(X_tech)
    train_surrogate(X_filtered, y_tech, "gradient_boosting")
        → GradientBoostingClassifier.fit()
    faithfulness_score()
        → 5-fold StratifiedKFold CV
        → accuracy, ROC-AUC, F1, majority baseline
    [--ablation: run_ablation() → identity/class variants]
    ▼
results/models/<technique>/surrogate.joblib
results/models/<technique>/faithfulness_metrics.json
results/models/<technique>/ablation_results.csv      (if --ablation)
results/models/technique_comparison.csv
    │
    ▼  python3 -m xaisphh.cli explain
for each technique:
    compute_shap_values(model, X_tech)   → TreeExplainer
    global_feature_importance()          → mean |SHAP| per feature
    save_summary_plot()                  → beeswarm PDF
    compute_interaction_values(model, X_tech[:2000])  → 3D interaction array
    save_interaction_heatmap()           → heatmap PDF
    lime_grid(model, X_tech, progress, n_grid=50)
    condition_frequency_table()          → most frequent LIME conditions
    ▼
results/explanations/<technique>/shap_global_importance.csv
results/explanations/<technique>/shap_summary_plot.pdf
results/explanations/<technique>/shap_interaction_heatmap.pdf
results/explanations/<technique>/lime_grid.csv
results/explanations/<technique>/lime_condition_frequency.csv
results/explanations/shap_comparison_by_technique.csv
    │
    ▼  python3 -m xaisphh.cli figures
_plot_convergence()     → best_so_far over iteration per run
_plot_importance()      → horizontal bar chart of mean |SHAP| per technique
    ▼
results/figures/convergence.pdf
results/figures/shap_importance_<technique>.pdf
    │
    ▼  python3 -m xaisphh.cli report
generate_report()       → assembles all outputs into paginated PDF
    ▼
results/report.pdf
```

---

## 10. Configuration Reference

### Technique Name Format

```
[SP|MP]-[CF|SR][-acceptance]
```

| Component | Values |
|-----------|--------|
| Mode | `SP` = single-point, `MP` = multi-point (population) |
| Selection | `CF` = Choice Function, `SR` = Simple Random |
| Acceptance | `LA`, `AILTA`, `SA`, `IOE`, `NAIVE` (SP only; MP has no acceptance suffix) |

Valid names: `SP-CF-LA`, `SP-CF-AILTA`, `SP-CF-SA`, `SP-SR-LA`, `SP-SR-AILTA`,
`SP-SR-SA`, `MP-CF`, `MP-SR`

### techniqueParameters Keys

| Key | Used by | Default | Meaning |
|-----|---------|---------|---------|
| `listLength` | LA | 50 | Late Acceptance history list length L |
| `initialTemp` | SA | 1000.0 | Simulated Annealing starting temperature |
| `decayRate` | SA | 0.99 | SA geometric cooling factor per step |
| `totalIterations` | AILTA | 100000 | Estimated iterations for AILTA decay calibration |
| `populationSize` | MP | 10 | Number of individuals in the population |
| `budgetScaling` | MP | (none) | Set to `per_member` to multiply budgetValue by populationSize |
| `wallClockCapMs` | All (iter budget) | 3600000 | Safety cap for HyFlex timer (1 hour) |

### Domain Names and Instance Indices

All CHeSC domains have 10 instances each (indices 0–9):
`SAT`, `BinPacking`, `FlowShop`, `TSP`, `VRP`, `PersonnelScheduling`

### Python CLI Options Summary

| Command | Key options |
|---------|------------|
| `load` | `--traces DIR` `--out DIR` `--allow-mixed` |
| `features` | `--interim DIR` `--out DIR` `--keep-scores` |
| `yates` | `--interim DIR` `--out DIR` `--clip-low FLOAT` `--clip-high FLOAT` `--divergence-factor FLOAT` |
| `train` | `--processed DIR` `--out DIR` `--model-type [gradient_boosting\|random_forest\|logistic_regression]` `--seed INT` `--ablation` `--pooled` |
| `explain` | `--results DIR` `--processed DIR` `--out DIR` `--n-lime-grid INT` `--n-interactions INT` `--pooled` `--seed INT` |
| `figures` | `--results DIR` `--interim DIR` `--out DIR` |
| `stats` | `--objectives CSV` `--out CSV` |
| `report` | `--interim DIR` `--processed DIR` `--models DIR` `--explanations DIR` `--out PDF` |

> **Note on paths:** `load` outputs to `data/interim/` (not `data/processed/`).
> `features` and `yates` both read from `--interim data/interim/`.
> `train` and `explain` read from `--processed data/processed/`.
