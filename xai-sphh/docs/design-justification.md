# Design Justification

| Component | What | Why chosen | Alternative rejected | Evidence |
|-----------|------|-----------|---------------------|----------|
| Selection: Choice Function | Scores heuristics by recency, improvement, and pair performance (f1, f2, f3) | Adaptive; learns which heuristics work well in combination; widely studied in HH literature | Simple Random (no learning) | Drake et al. (2012); CF is the standard adaptive selection in CHeSC |
| Selection: Simple Random | Uniform random heuristic selection | Baseline with no learning bias; isolates the contribution of acceptance and features | Choice Function | Used as baseline (SP-SR-LA) for all within-domain comparisons |
| Acceptance: Late Acceptance | Accepts if new objective <= objective L steps ago (list length L=50) | Simple, parameter-light; robust across domains | Simulated Annealing (temperature tuning), AILTA (complex decay) | Burke and Bykov (2017); L=50 from preliminary runs |
| Acceptance: AILTA | Adaptive threshold decaying from initial objective over total iterations | Adapts threshold to search progress; no temperature parameter | SA (fixed decay), LA (fixed list) | Lam and Li (2015) |
| Population: Multi-point (MP-CF) | Population of 10 solutions; each iteration applies heuristic to one member, replaces if improved | Maintains diversity; can escape local optima | Single-point only | Population size 10 from CHeSC defaults |
| Feature: feat_progress | Fraction of budget consumed | Allows surrogate to capture phase-dependent behaviour | | Required for AILTA decay modelling |
| Feature: feat_obj_norm | Current objective normalised by initial value | Scale-invariant representation of solution quality | Raw objective (domain-dependent scale) | |
| Feature: feat_gap_to_best | (current - best) / best | Measures distance from best known; scale-invariant | Absolute gap (not comparable across domains) | |
| Feature: feat_iters_since_improve | Iterations since last improvement | Proxy for stagnation detection | | |
| Feature: feat_improve_rate_50 | Fraction of last 50 iterations that improved | Smoothed recent improvement rate | Raw acceptance rate | Window of 50 from preliminary testing |
| Feature: feat_mean_logret_50 | Mean log-return over last 50 iterations | Captures recent search trajectory direction and magnitude | Raw deltas | Log-return is scale-invariant |
| Feature: feat_last_h{1,2,3} | Heuristic IDs applied in last 3 iterations | Captures recent heuristic sequence for CF pattern learning | Longer history (memory cost) | 3-step history sufficient for f2 pair scoring |
| Feature: feat_last_class{1,2,3} | Heuristic classes (LS/MUT/RR/XO) in last 3 iterations | Captures type-level patterns | | |
| Feature: feat_iters_since_accept | Iterations since last accepted move | Measures acceptance stagnation | | |
| Feature: feat_pop_diversity | Population diversity (MP only) | Tracks convergence of population | | Only computed for MP-CF |
| Feature: feat_pop_target_rank | Rank of target solution in population | Identifies whether weak or strong members are targeted | | Only computed for MP-CF |
| Feature: feat_llh_count | Number of low-level heuristics in domain | Constant within a domain; **excluded from surrogates in A5** | Included (acted as domain label in A4) | A4 feedback: inflated cross-domain SHAP |
| Surrogate model | Gradient Boosting Classifier | Handles feature interactions, non-linearities; best fidelity in preliminary tests | Random Forest, Logistic Regression | 5-fold CV ROC-AUC comparison |
| Budget | Per-domain iteration count from convergence curves | Ensures convergence within each domain; avoids wasted compute on slow domains | Fixed 100k for all domains | Convergence analysis (results/budgets/convergence.png) |
| Seed count | 10 independent seeds per cell | Provides run-to-run variance estimates; enables paired statistical tests | 1 (A4), 31 (CHeSC) | 10 is standard minimum for non-parametric tests |

## Changes since Assessment 4

| Change | Reason | Marker comment addressed |
|--------|--------|------------------------|
| 10 seeds per cell (was 1) | Enable statistical testing, estimate variance | Replication |
| Per-domain budgets from convergence (was fixed 100k) | Fair comparison within domain; feasible PS budget | Replication, CHeSC comparability |
| Drop CHeSC comparability claim | Budget, instance, and run count do not match CHeSC protocol | CHeSC comparability |
| Exclude feat_llh_count from surrogates | Constant within domain; acted as domain label | SHAP inconsistency |
| Per-domain surrogates (was pooled) | SHAP values are comparable within a domain | SHAP inconsistency |
| Use SHAP ranks/shares, not raw magnitudes | Raw magnitudes not comparable across techniques | SHAP inconsistency |
| Explicit research questions (RQ1-RQ4) | Analysis needs clear goals stated upfront | Overall |
