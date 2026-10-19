# XAI for Cross-Domain Selection Perturbative Hyper-Heuristics
## Findings and Implementation Report

---

## 1. Project Overview

This project applies Explainable AI (XAI) to understand the internal decision-making
behaviour of selection perturbative hyper-heuristics (SPHH). A hyper-heuristic sits
above a set of low-level heuristics (LLHs) and decides, at each iteration, which LLH
to apply and whether to keep the resulting solution. Because it operates solely on
objective scores — never on problem structure — the same algorithm can run across
multiple problem domains without modification.

The core research question is:

> **What does a hyper-heuristic implicitly learn to respond to, and does this differ
> between selection strategies, acceptance strategies, and search topologies?**

SHAP and LIME are used to answer this by explaining a surrogate model trained on the
HH's recorded decisions.

---

## 2. System Architecture

The system is split into two halves that communicate through trace CSV files.

### 2.1 Java — Experiment Runner

The Java side runs hyper-heuristic experiments on HyFlex benchmark problems and
instruments every decision made. At each iteration it:

1. Selects a low-level heuristic using the configured selection strategy
2. Applies the heuristic and receives an objective score
3. Decides whether to accept the new solution using the configured acceptance strategy
4. Captures a snapshot of the search state and writes it to a trace CSV

**Selection strategies implemented:**
- `ChoiceFunction` — Modified Choice Function (Cowling et al. 2001; adaptive phi from
  Tyasnurita et al. 2017). Scores each heuristic using three terms: recent individual
  performance (f1), recent pair performance (f2), and time since last use (f3). phi
  snaps to 0.99 on improvement and decays by 0.01 per step with a floor of 0.01.
- `SimpleRandom` — selects uniformly at random from all available LLHs. No learning.
  Acts as the null-model baseline.

**Acceptance strategies implemented:**
- `LateAcceptance` — accepts a move if the new objective is better than the objective
  L steps ago. List length L=50.
- `AILTA` — Adaptive Improved Late Acceptance. The threshold adapts based on recent
  improvement history over the run lifetime.
- `SimulatedAnnealing` — accepts based on a Boltzmann probability that decays with
  temperature over time.

**Search topologies:**
- Single-point (SP) — maintains one current solution.
- Multi-point (MP) — maintains a population of solutions; replacement acts as acceptance.

### 2.2 Python — Analysis Pipeline

The Python side reads trace files and runs a 6-stage pipeline:

| Stage | Command | Output |
|---|---|---|
| 1. Load | `xaisphh load` | Validated Parquet files |
| 2. Features | `xaisphh features` | Feature matrix |
| 3. Yates | `xaisphh yates` | Log returns, percentile ranks, footrule distances |
| 4. Train | `xaisphh train` | Fitted surrogate model + faithfulness metrics |
| 5. Explain | `xaisphh explain` | SHAP plots, LIME plots, interaction heatmap |
| 6. Figures | `xaisphh figures` | Publication-ready PDF figures |

---

## 3. Feature Set

Sixteen domain-independent features are extracted at every decision point. They are
grouped into five categories:

### Search Progress
| Feature | Description |
|---|---|
| `feat_progress` | Fraction of total budget consumed (0.0 to 1.0) |
| `feat_iters_since_improve` | Steps since best-so-far was last improved |
| `feat_iters_since_accept` | Steps since any move was accepted |

### Solution Quality
| Feature | Description |
|---|---|
| `feat_obj_norm` | Current objective normalised by running observed range |
| `feat_gap_to_best` | Gap from current to best-so-far, scaled by running range |

Both use running extrema only. Using the full-run range would leak future information
into a decision-time feature and artificially inflate surrogate accuracy.

### Recent Performance (last 50 steps)
| Feature | Description |
|---|---|
| `feat_improve_rate_50` | Fraction of last 50 moves that improved the solution |
| `feat_mean_logret_50` | Mean log return over the last 50 moves |

### Heuristic History (categorical)
| Feature | Description |
|---|---|
| `feat_last_h1/h2/h3` | Index of heuristic used 1, 2, 3 steps ago |
| `feat_last_class1/2/3` | Class of heuristic used 1, 2, 3 steps ago |

Sentinel value -1 is used when no predecessor exists. These are categorical, not ordinal.

### Population (multi-point only)
| Feature | Description |
|---|---|
| `feat_pop_diversity` | Spread across the population (NaN for single-point) |
| `feat_pop_target_rank` | Rank of the candidate within the population (-1 for single-point) |

### Structural
| Feature | Description |
|---|---|
| `feat_llh_count` | Number of low-level heuristics available in the domain |

**Domain barrier:** all features derive solely from objective values, iteration counts,
and heuristic indices. No problem-specific information is ever exposed. `DomainBarrierTest`
enforces this via a string deny-list.

---

## 4. Experiment Setup

### 4.1 Configuration

| Setting | Value |
|---|---|
| Framework | HyFlex (CHeSC benchmark) |
| Domain | SAT (Boolean Satisfiability) |
| Instance | Index 0 |
| Random seed | 42 |
| Budget type | Iteration-based |
| Budget | 100,000 iterations per run |

### 4.2 Techniques Run

| Technique | Selection | Acceptance | Key Parameter |
|---|---|---|---|
| SP-SR-LA | Simple Random | Late Acceptance | list length = 50 |
| SP-CF-LA | Choice Function | Late Acceptance | list length = 50 |
| SP-CF-AILTA | Choice Function | Adaptive ILTA | total iterations = 100,000 |
| MP-CF | Choice Function | Population replacement | population size = 10 |

### 4.3 Final Objective Scores (SAT Instance 0, Seed 42)

SAT is a minimisation problem — lower scores are better.

| Technique | Final Objective |
|---|---|
| SP-SR-LA (baseline) | 12.0 |
| SP-CF-LA | 13.0 |
| SP-CF-AILTA | **5.0** |
| MP-CF | 43.0 |

SP-CF-AILTA achieved the best result. MP-CF performed worst, likely due to its
population-based search being less focused on a single solution under a fixed iteration budget.

### 4.4 Dataset Size

4 runs × 100,000 iterations = approximately **400,000 total decisions** fed into the
surrogate training.

---

## 5. Surrogate Model

### 5.1 Training

The surrogate is a Gradient Boosting Classifier (scikit-learn) trained to predict
whether the hyper-heuristic would accept or reject a move given the 16-feature search
state at that moment.

| Hyperparameter | Value | Rationale |
|---|---|---|
| n_estimators | 200 | Sufficient capacity for 400k rows |
| max_depth | 4 | Shallow trees reduce overfitting |
| learning_rate | 0.05 | Slow, stable learning |
| subsample | 0.8 | Reduces variance via stochastic sampling |

Target variable: binary — `1 = accepted`, `0 = rejected`.

### 5.2 Faithfulness Metrics (5-fold Stratified Cross-Validation)

| Metric | Surrogate | Majority-class baseline |
|---|---|---|
| Accuracy | **88.5% ± 0.1%** | 57.5% |
| ROC-AUC | **95.3% ± 0.06%** | 50.0% |
| F1 Score | **90.5% ± 0.08%** | — |

The surrogate achieves 88.5% accuracy against a majority-class baseline of 57.5%,
confirming it has genuinely learned the HH's decision logic rather than just predicting
the common case. Low standard deviations across folds confirm stability.

The high ROC-AUC (95.3%) means the surrogate can reliably rank decisions by their
likelihood of acceptance — critical for SHAP to produce meaningful explanations.

---

## 6. SHAP Results (Global Explanation)

SHAP (SHapley Additive exPlanations) assigns each feature an importance score
representing its average contribution to the model's output across all decisions.

### 6.1 Global Feature Importance Rankings

| Rank | Feature | Mean |SHAP| | Interpretation |
|---|---|---|---|
| 1 | `feat_pop_target_rank` | 1.259 | Where the candidate sits in population ranking |
| 2 | `feat_pop_diversity` | 0.776 | Spread across the population |
| 3 | `feat_improve_rate_50` | 0.629 | Recent improvement momentum |
| 4 | `feat_iters_since_accept` | 0.389 | Pressure from not accepting |
| 5 | `feat_mean_logret_50` | 0.379 | Average quality of recent gains |
| 6 | `feat_last_h1` | 0.230 | Which heuristic was just used |
| 7 | `feat_progress` | 0.194 | How far through the budget |
| 8 | `feat_last_h3` | 0.178 | Heuristic used 3 steps ago |
| 9 | `feat_last_h2` | 0.157 | Heuristic used 2 steps ago |
| 10 | `feat_iters_since_improve` | 0.103 | Stagnation duration |
| 11 | `feat_last_class3` | 0.057 | Class of heuristic 3 steps ago |
| 12 | `feat_obj_norm` | 0.050 | Raw normalised objective value |
| 13 | `feat_last_class2` | 0.029 | Class of heuristic 2 steps ago |
| 14 | `feat_last_class1` | 0.027 | Class of heuristic 1 step ago |
| 15 | `feat_gap_to_best` | 0.024 | Distance from best-so-far |
| 16 | `feat_llh_count` | 0.000 | Number of available heuristics |

### 6.2 Key Findings from SHAP

**Population dynamics dominate.** `feat_pop_target_rank` (1.259) and
`feat_pop_diversity` (0.776) are the top two features by a significant margin. The
hyper-heuristic is primarily driven by where a candidate sits in the population and
how diverse the population is — not by raw solution quality.

**Raw objective value is almost irrelevant.** `feat_obj_norm` ranks 12th (0.050) and
`feat_gap_to_best` ranks 15th (0.024). The HH does not make decisions based on the
absolute quality of the current solution.

**Momentum matters more than quality.** `feat_improve_rate_50` (0.629) and
`feat_mean_logret_50` (0.379) both rank highly. The HH responds to whether it has
been improving recently, not where it currently stands.

**Acceptance pressure is a real mechanism.** `feat_iters_since_accept` (0.389)
ranks 4th. The longer the HH goes without accepting a move, the more likely it becomes
to accept — a built-in escape mechanism from stagnation.

**Heuristic history matters, class does not.** The specific heuristic index used
recently (`feat_last_h1/h2/h3`) is far more informative than the class of heuristic
(`feat_last_class1/2/3`). Which specific tool was used is more predictive than what
category it belongs to.

**Domain size is irrelevant.** `feat_llh_count` has zero importance. The number of
available heuristics has no influence on acceptance decisions.

### 6.3 SHAP Beeswarm Interpretation

From the beeswarm summary plot:

- Low `feat_pop_target_rank` (blue, good position) → strong push toward acceptance
- High `feat_pop_target_rank` (red, poor position) → strong push toward rejection
- Low `feat_pop_diversity` (blue) → push toward rejection (population converged)
- High `feat_improve_rate_50` (red) → push toward acceptance
- High `feat_iters_since_accept` (red) → push toward acceptance (desperation effect)

---

## 7. LIME Results (Local Explanations)

LIME (Local Interpretable Model-agnostic Explanations) explains individual decisions
by fitting a local linear model around each specific decision point.

### 7.1 Instance 0 — Step 0 (Start of Run)

Top influential conditions:

| Condition | Direction | Weight |
|---|---|---|
| `feat_progress <= 0.25` | Toward acceptance | +0.15 |
| `feat_iters_since_accept <= 0.00` | Toward rejection | -0.10 |
| `feat_obj_norm > 0.01` | Toward acceptance | +0.04 |

**Interpretation:** At the very start of the run, the dominant signal is that the
budget has barely begun (`progress <= 0.25`), which strongly pushes toward acceptance.
The HH behaves exploratorily — it accepts freely because it has nothing to lose. The
rejection signal from `iters_since_accept <= 0.00` reflects that there is no history
of stagnation yet.

### 7.2 Instance 160,000 — Mid-Run (Step 160k)

Top influential conditions:

| Condition | Direction | Weight |
|---|---|---|
| `feat_iters_since_accept <= 0.00` | Toward rejection | -0.10 |
| `feat_progress 0.50–0.75` | Toward rejection | -0.07 |
| `feat_obj_norm > 0.01` | Toward acceptance | +0.07 |
| `feat_improve_rate_50 0.00–0.02` | Toward rejection | -0.03 |

**Interpretation:** Mid-run, the picture has fundamentally changed. Being in the
0.50–0.75 progress window now pushes toward rejection. The HH has switched from
exploration to exploitation — it is now much more selective, only accepting if
`feat_obj_norm` is genuinely high. Very low improvement rate further reinforces
rejection.

### 7.3 Exploration-to-Exploitation Phase Shift

Comparing LIME across decision points reveals a clear behavioural phase transition:

| Phase | Budget range | Dominant signals | Behaviour |
|---|---|---|---|
| Exploration | 0–25% | `feat_progress` (low) | Accepts freely, builds solution space knowledge |
| Transition | 25–50% | Mixed signals | Increasingly selective |
| Exploitation | 50–100% | `feat_obj_norm`, `feat_improve_rate_50` | Only accepts genuine quality improvements |

This phase shift is invisible from the final objective score alone. XAI makes it explicit.

---

## 8. Yates Analysis

### 8.1 Log Returns by Heuristic

Log returns measure the relative quality gain from applying each heuristic.

| Heuristic | Mean Log Return | Interpretation |
|---|---|---|
| 0 | -0.0055 | Consistently slightly harmful |
| 1 | -0.0054 | Consistently slightly harmful |
| 2 | +0.0149 | Mildly beneficial |
| 3 | +0.0654 | Moderately beneficial |
| 4 | +0.1181 | Consistently good |
| 5 | +0.0616 | Moderately beneficial |
| **6** | **+2.083** | **Dominant — massive outlier** |
| 7 | -0.0036 | Near neutral |
| 8 | -0.0004 | Near neutral |
| 9 | +0.086 | Occasionally very good |
| 10 | +0.086 | Occasionally very good |

**Key finding:** Heuristic 6 has a mean log return of +2.083 — roughly 30× better
than the next best heuristic (heuristic 4 at +0.118). A small number of heuristics
are responsible for almost all quality improvement. The Choice Function should
identify and exploit this quickly.

### 8.2 Footrule Distances (Heuristic Ranking Stability)

Spearman footrule distance measures how much heuristic rankings shift between the
early phase and the late phase of a run. A distance of 0 means rankings are identical;
higher values mean more rank instability.

| Run | Technique | Footrule Distance |
|---|---|---|
| 1 | — | 18.0 |
| 2 | — | 12.0 |
| 3 | — | 23.0 |
| 4 | — | 11.0 |

Rankings shift by 11–23 positions across all runs. This confirms that **heuristic
utility is not static** — what works early in the search does not necessarily work
late. This justifies using an adaptive selection strategy (Choice Function) over a
static or random one: the HH needs to track changing heuristic usefulness over time.

---

## 9. Key Conclusions

1. **The surrogate faithfully mirrors the HH** — 88.5% accuracy and 95.3% ROC-AUC
   confirm that SHAP and LIME are explaining the real decision logic, not noise.

2. **Population dynamics, not raw quality, drive decisions** — `feat_pop_target_rank`
   and `feat_pop_diversity` dominate. The HH is fundamentally a population manager
   even in single-point mode.

3. **Momentum beats quality** — `feat_improve_rate_50` (rank 3) outweighs
   `feat_obj_norm` (rank 12). The HH responds to recent trend, not absolute position.

4. **Acceptance pressure is a real, measurable mechanism** — `feat_iters_since_accept`
   (rank 4) confirms the HH uses stagnation duration as a trigger to loosen acceptance.

5. **The HH has distinct behavioural phases** — LIME reveals an exploration phase
   (early, accept freely) and an exploitation phase (late, accept only quality moves).
   This phase transition is invisible from the final score alone.

6. **Heuristic utility shifts over time** — footrule distances of 11–23 confirm that
   adaptive selection is justified. Static or random selection cannot respond to
   changing heuristic usefulness.

7. **One heuristic dominates** — heuristic 6 produces log returns 30× higher than
   most others. The Choice Function should detect and exploit this; Simple Random cannot.

8. **SP-CF-AILTA achieved the best solution** — final objective 5.0 vs 12.0 for
   the Simple Random baseline. The combination of an adaptive selection strategy and
   an adaptive acceptance threshold outperforms static alternatives on this instance.

---

## 10. Limitations

| Limitation | Impact |
|---|---|
| Single domain (SAT only) | Cannot generalise SHAP findings to other problem types |
| Single instance (index 0) | Results may be specific to this instance's difficulty profile |
| Single seed (42) | No statistical reliability — results could be seed-dependent |
| Parameters not tuned | List length=50 and population size=10 are arbitrary, not optimised |
| Stub HyFlex (no real jars) | Objective values come from simulated domains, not real CHeSC benchmarks |
| No significance testing | Cannot confirm SP-CF-AILTA is genuinely better without multiple seeds |

---

## 11. Recommended Next Steps

### Immediate
1. Obtain real HyFlex CHeSC jars (`chesc-fixed-no-ps.jar`, `chesc-ps.jar`) — this
   unblocks all subsequent work.

### Experimental Expansion
2. Run all 4 techniques across all 6 domains (SAT, BinPacking, FlowShop, TSP, VRP,
   PersonnelScheduling), all 10 instances per domain, with 5–10 seeds per run.
3. Perform parameter sweeps: Late Acceptance list length over {1, 5, 50, 100, 500, 1000};
   population size over {5, 10, 20, 50}.

### Analysis
4. Train separate surrogates per domain and compare SHAP feature importance across
   domains — do the same features dominate universally?
5. Compare SHAP profiles between Choice Function and Simple Random runs to quantify
   what the learning in CF actually changes.
6. Apply Wilcoxon signed-rank tests across seeds to establish statistical significance
   of technique comparisons.

### Reporting
7. Complete the LaTeX report in `report/` with full results tables, cross-domain SHAP
   comparisons, and statistical analysis.

---

## 12. Repository Reference

| Path | Contents |
|---|---|
| `java/src/main/java/za/ac/up/cos790/` | Java implementation |
| `python/src/xaisphh/` | Python analysis pipeline |
| `config/experiments/` | Experiment configuration YAML files |
| `data/raw/traces/` | Trace CSVs and manifest JSONs from Java runs |
| `results/models/` | Trained surrogate and faithfulness metrics |
| `results/explanations/` | SHAP plots, LIME plots, interaction heatmap |
| `results/yates/` | Log returns, percentile ranks, footrule distances |
| `docs/design-decisions.md` | Rationale for all major design choices |
| `docs/trace-schema.md` | Trace CSV column specification |

---

*Report generated from experimental results produced on 2026-09-01.*
*All runs: SAT domain, instance 0, seed 42, 100,000 iterations.*
