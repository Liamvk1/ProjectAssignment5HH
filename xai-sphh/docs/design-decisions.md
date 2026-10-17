# Design Decisions

This document records resolved design questions and their rationale. Each entry
corresponds to a decision made across the three member implementation documents
(Member 2 Q08-Q20, Member 4 DD-01 to DD-08, Member 1+3 Decisions 21-31).

## DD-01: Selection strategy algorithm

**File:** `selection/ChoiceFunction.java`, `selection/SimpleRandom.java`

**Decision.** The Modified Choice Function (Cowling, Kendall and Soubeiga 2001;
adaptive phi rule from Drake, Ozcan and Burke 2012) is the primary research
vehicle. SimpleRandom is the baseline.

**Phi update rule attribution.** The adaptive phi rule (snap to 0.99 on improvement,
decay 0.01, floor 0.01) is taken from: Drake, J.H., Ozcan, E. and Burke, E.K. (2012),
"An improved choice function heuristic selection for cross domain heuristic search",
Parallel Problem Solving from Nature, PPSN XII, Lecture Notes in Computer Science
vol. 7492, pp. 307-316, Springer, Berlin/Heidelberg. This replaces an earlier
attribution to Tyasnurita, Ozcan and John (2017), which is incorrect.

**Resolution of coordination conflict.** Member 4 DD-01 proposed a fixed-phi scheme
(f1 and f2 using phi=0.5, additive alpha/beta/delta weights). Member 2 Q09 proposed
the Modified Choice Function with adaptive phi (snap to 0.99 on improvement, decay
0.01, floor 0.01). Member 2's rule was adopted because its constants are published and
validated across all six CHeSC domains (Drake et al. 2012), whereas Member 4's additive
update constants have no cited source. The dropped alternative is recorded here: fixed
phi=0.5 with additive alpha/beta/delta updates, discarded because its constants cannot
be attributed.

## DD-02: Acceptance strategy parameters

**File:** `acceptance/LateAcceptance.java`, `acceptance/SimulatedAnnealing.java`,
`acceptance/AILTA.java`

**Decision.** Late Acceptance Hill Climbing is the baseline (list length L=50).
Simulated Annealing is retained as an ablation. AILTA is added to satisfy the
assessment requirement that names four criteria explicitly (Member 4 DD-02).

**Resolution of list length conflict.** Member 2 Q18 specified L=50; Member 4
DD-02 specified L=100. Neither value is justified as a tuned optimum; both documents
acknowledge this. L=50 was adopted since Member 2 is the authority for acceptance
strategy implementation. Both values should be included in the parameter sweep over
{1, 5, 50, 100, 500, 1000} before a final value is reported.

## DD-03: Feature set

**File:** `state/FeatureExtractor.java`

**Decision.** The feature set matches Decision 28 (Member 1+3) and is confirmed by
Member 4 DD-03. Active features: `feat_llh_count`, `feat_progress`, `feat_obj_norm`,
`feat_gap_to_best`, `feat_iters_since_improve`, `feat_improve_rate_50`,
`feat_mean_logret_50`, `feat_last_h1/h2/h3`, `feat_last_class1/2/3`,
`feat_iters_since_accept`, `feat_pop_diversity`, `feat_pop_target_rank`.

All features are domain-independent; `DomainBarrierTest` enforces this.

**Normalisation constraint:** `feat_obj_norm` and `feat_gap_to_best` use running
observed extrema only (not the full-run range), because using the full range leaks
future information into decision-time features and inflates surrogate accuracy for
the wrong reason.

## DD-04: Budget policy

**File:** `experiment/BudgetPolicy.java`

**Decision.** Both budget modes are used on different authority (Member 4 DD-04):
- `WALL_CLOCK` (time-based): for CHeSC-comparable protocol runs.
- `APPLICATIONS` (iteration-based, default 100,000): for all runs that will be
  analysed. Fixed iteration count keeps trace volume and reproducibility independent
  of machine speed.

The CHeSC machine-factor scaling for `WALL_CLOCK` is noted from Member 4 DD-04 and
should be applied when running benchmark comparisons.

**Extension (Item 6): multi-point budget scaling.**
Multi-point runs with population size p share the same total iteration budget as
single-point runs by default (`budgetScaling: none`). This means each individual
receives roughly 1/p times as many heuristic applications, which may disadvantage
multi-point search on a per-individual basis.

An alternative mode (`budgetScaling: per_member`) scales the iteration budget by p,
so each individual receives the same expected number of applications as a single-point
run. This mode is selectable via the `budgetScaling` YAML key.

**Default:** `none` (unchanged from previous behaviour; all existing configs are
unaffected). The `per_member` mode should be used when the research question is
specifically about per-individual quality rather than total computational budget. The
chosen mode is recorded in the run manifest for traceability.

## DD-05: Surrogate model family

**File:** `python/src/xaisphh/surrogate/train.py`

**Decision.** A gradient-boosted tree. Handles mixed feature types and non-linear
interactions; SHAP supports it natively. The linear-model alternative is more
directly interpretable but cannot represent interactions between heuristic identity
and search state without manually engineered terms, reintroducing domain-specific
judgement.

## DD-06: SHAP vs LIME scope

**File:** `python/src/xaisphh/explain/shap_global.py`, `explain/lime_local.py`

**Decision.** Both are implemented with distinct roles: SHAP for global feature
importance over a whole run; LIME for local explanations at specific decision points.
Cases where they disagree are reported.

## DD-07: f2 pair update rule

**File:** `selection/ChoiceFunctionTerms.java`

**Decision.** Same exponential decay as f1, per pair (i, j). Resolved as part of
DD-01: the Modified Choice Function's adaptive phi governs both f1 and f2 decay.
All other f2 entries carry over unchanged until that pair recurs.

## DD-08: Log return for non-positive objectives

**File:** `instrumentation/CsvTraceWriter.java`, `python/src/xaisphh/yates/log_returns.py`

**Decision.** Write an empty field, not NaN or infinity. An empty CSV field parses
cleanly as a missing float in Pandas; the literal string "NaN" causes dtype inference
to produce an object column that then requires cleaning wherever it is read.

This matches Decision 27 (Member 1+3) and Member 4 DD-08. The `log_return` field in
`TraceRecord` stores NaN internally; the CSV writer translates it to an empty field
on write.

**Extension (Item 2): log-return clipping.**
Near-zero objective values can cause log ratios to blow up (e.g., heuristic 6 showed
a mean log return of +2.083 in baseline SAT runs where the incumbent objective
approached zero). To suppress this artefact without discarding the row, valid log
returns are clipped to the range [-10, +10] before summary statistics are computed.

**Default clip range:** [-10, +10]. This is configurable via `--clip-low` and
`--clip-high` in the `yates` pipeline stage. The clip is applied only to the Python
analysis; the Java trace writer still records the raw value (or empty for non-positive
objectives). A diagnostic warning is emitted for any heuristic whose mean log return
differs from its median by a factor exceeding 2.0 (configurable via
`--divergence-factor`).
