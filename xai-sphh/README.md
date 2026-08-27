# xai-sphh: Explainable AI for Selection Perturbative Hyper-Heuristics

This project applies explainable AI techniques to cross-domain selection perturbative hyper-heuristics evaluated on the HyFlex benchmarking framework. Every decision the hyper-heuristic makes is logged as a trace; those traces are analysed offline to explain which low-level heuristics were effective, when, and why. The Java side runs the search and writes traces; the Python side reads them and produces explanations.

## Prerequisites

| Tool | Version |
|------|---------|
| Java | 21 |
| Gradle | 8.x (wrapper included) |
| Python | 3.11 or later |
| pip | 23 or later |

## Placing the HyFlex jars

HyFlex is vendored locally because the original distribution is unreliable. Obtain the HyFlex jar (`HyFlex.jar`) and any domain jars (e.g. `chesc.jar`) and place them under:

```
lib/hyflex/
```

The build picks up all `*.jar` files in that directory via a `fileTree` dependency. If the directory is empty the Gradle configuration still loads, but `javac` will report missing symbols for any class that extends a HyFlex type.

## Building

```bash
./gradlew build
```

Running tests only:

```bash
./gradlew test
```

## Running one experiment

```bash
./gradlew run --args="config/experiments/baseline.yaml"
```

Or with the assembled jar:

```bash
java -jar build/libs/xai-sphh-0.1.0-SNAPSHOT.jar config/experiments/baseline.yaml
```

Traces are written to the `outputDirectory` specified in the config file (default: `data/raw/traces/`).

## Python pipeline

Install the package in editable mode:

```bash
pip install -e python/
```

Run the full pipeline over a directory of traces:

```bash
python -m xaisphh.cli load   --traces data/raw/traces/ --out data/interim/
python -m xaisphh.cli features --interim data/interim/ --out data/processed/
python -m xaisphh.cli yates  --processed data/processed/ --out results/tables/
python -m xaisphh.cli train  --processed data/processed/ --out results/
python -m xaisphh.cli explain --results results/ --out results/figures/
python -m xaisphh.cli figures --results results/ --out report/figures/
```

## Repository layout

```
xai-sphh/
├── build.gradle            Gradle build (Java 21, SnakeYAML, Jackson, JUnit 5)
├── lib/hyflex/             Vendored HyFlex jars (place here manually)
├── java/src/               Java source tree
│   ├── main/java/za/ac/up/cos790/
│   │   ├── Main.java
│   │   ├── config/         RunConfig record, ConfigLoader
│   │   ├── hyperheuristic/ Base class, SelectionStrategy, AcceptanceStrategy
│   │   ├── selection/      SimpleRandom, ChoiceFunction stubs
│   │   ├── acceptance/     NaiveAcceptance, ImprovingOrEqual, LateAcceptance, SA stubs
│   │   ├── state/          SearchState snapshot, FeatureExtractor
│   │   ├── instrumentation/TraceRecord, TraceWriter, CsvTraceWriter, RunManifest
│   │   ├── domain/         DomainRegistry, HeuristicCatalogue
│   │   └── experiment/     ExperimentRunner, BudgetPolicy, SeedPolicy
│   └── test/               JUnit 5 stub tests
├── python/src/xaisphh/     Python analysis package
│   ├── io/                 Schema definition and trace loader
│   ├── features/           Feature matrix assembly
│   ├── yates/              Reference measures (log returns, percentiles, footrule)
│   ├── surrogate/          Surrogate model training and faithfulness evaluation
│   ├── explain/            SHAP and LIME entry points
│   └── figures/            Shared matplotlib style
├── config/                 Feature and experiment configuration YAML files
├── data/                   Trace data (not committed; only .gitkeep markers)
├── results/                Analysis outputs (not committed; only .gitkeep markers)
├── report/                 LaTeX report source
├── scripts/                Shell helper scripts
└── docs/                   Design decisions and trace schema specification
```

See `docs/trace-schema.md` for the trace file column specification.
See `docs/design-decisions.md` for open design questions and rationale.
