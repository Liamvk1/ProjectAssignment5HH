## Task
Java 21, Gradle, HyFlex vendored under `lib/hyflex/`. Python 3.11, the `xaisphh` package.

## Background you need in order to make correct choices

The project logs every decision a hyper-heuristic makes so that an offline surrogate model can reproduce and then explain the selection policy. That downstream requirement reaches back into decisions that look, on the surface, like ordinary tuning choices. A weighting scheme that cannot be written down as a fixed rule cannot be recovered exactly by a surrogate model, a feature that is not domain independent breaks the domain barrier the whole cross-domain comparison depends on, and a budget definition that is not fixed in one place cannot be compared across runs or against published CHeSC results.

The six CHeSC domains have objective values that differ by orders of magnitude, so no threshold in this project may be expressed directly in objective units, and no numeric constant may be attributed to a source that does not state it. Where a value has been assumed rather than published, that is recorded as an assumption rather than presented as settled.

## Question to entry map

| Entry | File | Topic |
| --- | --- | --- |
| DD-01 | `selection/ChoiceFunction.java`, `selection/SimpleRandom.java` | Selection strategy algorithm and Choice Function scoring |
| DD-02 | `acceptance/LateAcceptance.java`, `acceptance/AILTA.java` | Acceptance strategy parameters |
| DD-03 | `state/FeatureExtractor.java`, `config/features.yaml` | Default feature set |
| DD-04 | `experiment/BudgetPolicy.java` | Budget policy |
| DD-05 | `python/src/xaisphh/surrogate/train.py` | Surrogate model family |
| DD-06 | `python/src/xaisphh/explain/shap_global.py`, `explain/lime_local.py` | SHAP vs LIME scope |
| DD-07 | `selection/ChoiceFunctionTerms.java` | f2 pair update rule |
| DD-08 | `instrumentation/TraceRecord.java` | Log return handling for non-positive objectives |

## DD-01: selection strategy algorithm

**File:** `selection/ChoiceFunction.java`, `selection/SimpleRandom.java`

**Decision.** The Choice Function (Cowling, Kendall, Soubeiga 2001) is the primary research vehicle, chosen for its pairwise term, which captures the sequential interaction effect between consecutively applied heuristics that a single-point method could otherwise not observe. SimpleRandom remains the baseline. The single-point framework additionally requires random gradient and reinforcement learning with a tabu list as further selection techniques, so the configurable selection/acceptance framework supports four strategies.

**Score.** `f(h_j) = α · f1(h_j) + β · f2(h_i, h_j) + δ · f3(h_j)`, where:

- f1 (individual performance) and f2 (pairwise performance, h_i to h_j) both use exponential decay with phi = 0.5, no windowing: `f1(h_j) = I(h_j) + phi · f1_prev(h_j)`, `f2(h_i, h_j) = I(h_j | h_i) + phi · f2_prev(h_i, h_j)`, where I is the log return of the call just made.
- f3(h_j) is elapsed CPU time since h_j was last applied.
- Weights initialise as alpha = beta = 1, delta = 0.01. After each call, alpha and beta move by 0.01 (towards 1.0 on an improving call, towards a floor of 0.01 otherwise), and delta is set to `1 - (alpha + beta) / 2` on every update, so a stalling search shifts weight towards f3.

**Reason.** This is a published scoring rule that requires no per-domain tuning, and the pairwise term is the reason Choice Function was chosen over a single-point score in the first place.

**Coordination note.** Member 2's Q08 and Q09 resolve the same two files with a different rule: the Modified Choice Function's adaptive phi (snap to 0.99 on an improving move, floor 0.01, f3 weight `1 - phi`), justified there by the fact that its constants are published and validated across all six CHeSC domains, whereas the additive alpha/beta/delta update here has no cited source for its constants. `ChoiceFunction.java` and `ChoiceFunctionTerms.java` cannot carry both rules at once. This needs reconciling with Member 2 before either version is merged as the implementation; whichever is dropped should be kept in this document as the rejected alternative, with a reason.

## DD-02: acceptance strategy parameters

**File:** `acceptance/LateAcceptance.java`, `acceptance/AILTA.java`

**Decision.** The assessment specifies four move acceptance criteria: accept all moves, improving or equal, late acceptance hill climbing, and adaptive iteration limited threshold accepting (AILTA). `SimulatedAnnealing.java` is removed; `AILTA.java` is implemented in its place to match the assessment's scope, since the specification names AILTA explicitly and not simulated annealing.

**Defaults.**
- Late Acceptance: list length L = 100.
- AILTA: iteration window of 100 calls before the threshold decays, initial threshold of 2% of the starting objective value, decaying linearly to 0 over the run.

**Reason.** Matching the assessment's named criteria list takes priority over keeping an acceptance strategy that is not on that list.

**Coordination note.** Member 2's Q17 keeps `SimulatedAnnealing.java` in the codebase as an ablation against Late Acceptance, which is their chosen baseline, and does not implement AILTA. That is a direct conflict with removing `SimulatedAnnealing.java`: either the class stays for Member 2's ablation and is not removed, or AILTA replaces it and Member 2's ablation loses its comparison point. This also means Late Acceptance now has two candidate defaults recorded, L = 100 here against L = 50 in Member 2's Q18. Both list lengths are unjustified starting points rather than tuned values, so resolving this is a matter of picking one default and updating whichever document is not authoritative, not of re-deriving the value.

## DD-03: feature set

**File:** `state/FeatureExtractor.java`, `config/features.yaml`

**Decision.** The default feature set is the normalised objective value, recent improvement rate, iterations since the last improvement, fraction of budget used, and the class and identity of preceding heuristics: `feat_obj_norm`, `feat_improve_rate_50`, `feat_iters_since_improve`, `feat_progress`, and `feat_last_h*`/`feat_last_class*` in the trace schema. All are domain independent, as the domain barrier requires.

**Reason.** This is the feature set the assessment specifies for the surrogate model, so `config/features.yaml` and `FeatureExtractor.FEATURE_NAMES` are updated to it, replacing the earlier placeholder list.

**Coordination note.** This matches Member 3's Decision 28 column for column, including the running-extrema normalisation requirement for `feat_obj_norm` and the categorical, sentinel `-1` treatment of `feat_last_h*`/`feat_last_class*`. Member 3's document is the implementation record for this feature set; this entry is confirmation that the two resolutions agree, not a second implementation to merge.

## DD-04: budget policy

**File:** `experiment/BudgetPolicy.java`

**Decision.** Both budget types are used, on different authority.
- `WALL_CLOCK` = 600,000 ms nominal, scaled by the CHeSC benchmarking tool's machine factor rather than hard-coded to 600 s, for CHeSC-comparable protocol runs.
- `APPLICATION_COUNT` = fixed at 100,000 applications, used for the reduced set of runs that get full per-decision trace logging. Fixing the count is a team decision rather than assessment-mandated, taken to keep trace volume and reproducibility independent of the benchmarking machine's speed for that reduced set.

**Reason.** A CHeSC-comparable protocol needs the machine-scaled wall clock budget; a reproducible, fully-traced subset needs a budget that does not depend on machine speed at all. Neither requirement covers the other, so both are kept.

**Coordination note.** This matches Member 3's Decision 24 (`APPLICATIONS` default cap 100,000, `WALL_CLOCK` default ten minutes) under different names for the same two modes. Member 3's document is the implementation record; the CHeSC machine-factor scaling for `WALL_CLOCK` is the one detail not already stated there and should be carried across.

## DD-05: surrogate model family

**File:** `python/src/xaisphh/surrogate/train.py`

**Decision.** A gradient-boosted tree, since it handles mixed feature types and non-linear interactions, and SHAP supports it natively. No linear-model alternative is adopted.

**Reason.** The alternative, a linear model, is more directly interpretable but cannot represent the interaction between a heuristic's identity and the search state without manually engineered interaction terms, which reintroduces the domain-specific judgement the domain barrier is meant to keep out of this layer. A tree-based model captures that interaction structure from the raw feature columns.

**Consequence.** `train_surrogate`, `save_surrogate` and `load_surrogate` in `train.py` are still stubs (`NotImplementedError`). Implementing them, and the corresponding faithfulness evaluation in `surrogate/evaluate.py`, is the next step and is not yet covered by any member's document.

## DD-06: SHAP vs LIME scope

**File:** `python/src/xaisphh/explain/shap_global.py`, `explain/lime_local.py`

**Decision.** Both are implemented, with distinct roles rather than one chosen over the other. SHAP carries the global account of which heuristics and state features matter overall; LIME carries the local account of why one heuristic was selected at one specific point in the search. Cases where the two disagree are reported, since a heuristic that matters globally but not locally behaves differently from one that matters only in particular states.

**Reason.** The project's explanatory claim spans both scales: which heuristics matter across a whole run, and why a specific decision was made at a point of interest such as the first move after a long stagnation. Choosing only one would leave one of those two questions unanswered.

**Consequence.** `compute_shap_values`, `global_feature_importance` and `save_summary_plot` in `shap_global.py`, and `explain_instance` and `save_explanation_plot` in `lime_local.py`, are still stubs (`NotImplementedError`), pending DD-05's surrogate model being trainable.

## DD-07: f2 pair update rule

**File:** `selection/ChoiceFunctionTerms.java`

**Decision.** The same exponential decay as f1, applied per pair (h_i, h_j), with phi = 0.5 and no separate windowing, as set out under DD-01. f2 is a matrix indexed by (i, j), updated only on the pair actually observed each call; all other entries carry over unchanged, with decay applying implicitly the next time that pair recurs.

**Reason.** The published Choice Function definition does not state a decay or windowing scheme for f2, so the same rule as f1 was chosen rather than introducing a second, unpublished mechanism with its own free parameter.

**Coordination note.** This shares DD-01's conflict with Member 2's Q08 and Q09. If DD-01's alpha/beta/delta scheme is dropped in favour of Member 2's Modified Choice Function rule, this entry's phi = 0.5 decay for f2 is dropped with it, since Member 2's rule uses a single adaptive phi for both f1 and f2 rather than a fixed 0.5.

## DD-08: log return handling for non-positive objectives

**File:** `instrumentation/TraceRecord.java`

**Decision.** Write an empty field, not NaN and not infinity. A NaN literal in a CSV column breaks Pandas dtype inference on load, whereas an empty field parses cleanly as a missing value. This overrides `docs/trace-schema.md`, which is updated to match. The Python analysis layer treats `log_return` as a nullable float.

**Reason.** The failure mode of writing NaN is silent: it loads, but as a column with a mixed or object dtype rather than a float column with a missing entry, which then has to be cleaned up wherever the trace is read rather than once at the point it is written.

**Coordination note.** This matches Member 3's Decision 27, which sets the same guard for the same reason in the same class, so the two documents agree. `docs/trace-schema.md` still needs the correction from "written as NaN" to "written as an empty field" applied; as of this document that correction has not yet been made.

## Tests

- `DomainBarrierTest` and `TraceSchemaTest` already exist and pass, and constrain DD-03 and DD-08 respectively; neither is new work from this document.
- No test yet exists for DD-01/DD-07's scoring rule, since `ChoiceFunction.select` and `recordOutcome` are still stubs pending the coordination note above being resolved.
- No test yet exists for DD-05 or DD-06, since `train_surrogate`, `compute_shap_values` and `explain_instance` are still `NotImplementedError` stubs.

## Acceptance criteria

1. Every decision is recorded as decision, reason and consequence, with published values attributed and every assumption marked as one.
2. No numeric constant is attributed to a source that does not state it.
3. Where this document's resolution duplicates or conflicts with another member's document for the same file, that is recorded rather than merged silently.
4. No feature in DD-03 or state observed by DD-01 encodes problem-specific information; `DomainBarrierTest` continues to pass.
5. `docs/trace-schema.md` is corrected to match DD-08.
6. `./gradlew test` and the Python test suite both pass once the stubs referenced above are implemented.
