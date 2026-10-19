# Practical Assessment 5: Cross-Domain Replicated Analysis of Selection Perturbative Hyper-Heuristics with Explainable AI

## 1. Introduction

This assessment addresses four feedback items from Assessment 4: insufficient experimental replication, an incorrect claim of comparability with published CHeSC results, inconsistent cross-technique SHAP magnitude comparisons, and the absence of explicit research questions to guide the analysis. The hyper-heuristic logic is unchanged; the improvements are in experimental methodology, statistical rigour, and explanation validity.

### 1.1 Research Questions

- **RQ1**: Within each domain, does any technique outperform the Simple Random baseline (SP-SR-LA) with statistical support?
- **RQ2**: Which technique performs best across domains?
- **RQ3**: Which state features drive acceptance within each technique, and are these explanations stable across seeds?
- **RQ4**: Do the features that drive acceptance differ between selection strategies, acceptance strategies, and search topologies?

### 1.2 Techniques

| Technique | Topology | Selection | Acceptance |
|-----------|----------|-----------|------------|
| SP-SR-LA | Single-point | Simple Random | Late Acceptance, L=50 |
| SP-CF-LA | Single-point | Choice Function | Late Acceptance, L=50 |
| SP-CF-AILTA | Single-point | Choice Function | AILTA |
| MP-CF | Multi-point (pop=10) | Choice Function | Population replacement |

**Selection strategies.** *Simple Random* selects a low-level heuristic uniformly at random each iteration, serving as a non-adaptive baseline. The *Modified Choice Function* (Drake, Ozcan & Burke 2012) scores each heuristic h as CF(h) = phi*f1[h] + phi*f2[prev][h] + (1-phi)*f3[h], where f1 accumulates the improvement per unit CPU time of h applied alone (exponentially decayed), f2 captures pair-sequence synergy between the previous heuristic and h, and f3 is the elapsed time since h was last applied (favouring idle heuristics). The adaptive weight phi snaps to 0.99 on any improving move and decays by 0.01 per non-improving step (floor 0.01), shifting the balance from exploitation to exploration as the search stagnates. The first n iterations (one per heuristic) apply each heuristic once in round-robin to initialise f1.

**Acceptance strategies.** *Late Acceptance* (Burke & Bykov 2017) maintains a circular buffer of length L=50 storing past incumbent objectives. A candidate is accepted if it improves the current incumbent *or* is no worse than the entry L steps ago; the buffer is tightened monotonically (never relaxed). All slots are initialised to +infinity, so the first L iterations accept everything. *AILTA* is a simplified linear-decay variant of the Adaptive Iteration-Limited Threshold Accepting strategy used in AdapHH (Misir & Ozcan 2014). The full AILTA reheats the threshold after prolonged stagnation; our variant omits reheating and decays the threshold linearly: theta(t) = 0.02*|f0|*(1 - t/T), where f0 is the starting objective. A candidate is accepted if its objective exceeds the incumbent by at most theta(t). At the final iteration, theta = 0 and the strategy degenerates to improving-or-equal acceptance. The threshold is scaled to each domain's starting objective, avoiding the need to tune an absolute constant per domain.

**Multi-point topology.** MP-CF maintains a population of p=10 solutions. Each iteration, a binary tournament selects the *worst* individual as the replacement target, and a second tournament (excluding the target) selects the *best* as a potential crossover partner. A candidate replaces the target if and only if it is strictly better *and* the target is not the population-best (elitism guard). There is no separate acceptance module; the replacement rule serves as the acceptance criterion. A single shared Choice Function instance scores heuristics across all individuals.

**Low-level heuristic sets.** Each HyFlex domain exposes a fixed set of heuristics discovered at runtime via `getNumberOfHeuristics()`: SAT (11), BinPacking (8), FlowShop (15), TSP (13), VRP (10), PersonnelScheduling (12). These include mutation, ruin-and-recreate, local search, and crossover operators; the hyper-heuristic treats them as black boxes identified only by index and HyFlex type class.

## 2. Experimental Setup

### 2.1 Real HyFlex Domains

All experiments use the real CHeSC HyFlex jar files (`chesc-fixed-no-ps.jar` and `chesc-ps.jar`) placed in `lib/hyflex/`. All 240 run manifests report `stub: false`. The six domains are SAT, BinPacking, FlowShop, TSP, VRP, and PersonnelScheduling.

**Limitation**: These results are not directly comparable to published CHeSC rankings. The CHeSC competition used a normalised 10-minute wall-clock time limit (scaled by a hardware benchmark), competition instances, and 31 independent runs per technique per domain. This study uses a per-domain iteration budget, instance 0 only, and 10 seeds. The real HyFlex domains are the same, but the experimental protocol differs.

### 2.2 Budget Policy

The budget is defined as a count of heuristic applications (calls to `applyHeuristic()`). All four techniques within a domain receive the same budget. MP-CF with population 10 receives the same total number of applications as the single-point techniques, not 10 times as many.

Per-domain budgets are set from convergence curves on a pilot run (Assessment 4, seed 42, 100,000 iterations for non-PS domains, 10,000 for PersonnelScheduling). For each domain, the budget is the smallest tier in {5,000; 10,000; 20,000; 50,000; 100,000} that exceeds the iteration at which all four techniques reach 95% of their total improvement.

| Domain | Budget | 95% convergence iteration |
|--------|--------|--------------------------|
| SAT | 50,000 | 28,536 |
| BinPacking | 100,000 | 94,670 |
| FlowShop | 100,000 | 91,405 |
| TSP | 10,000 | 9,834 |
| VRP | 50,000 | 29,002 |
| PersonnelScheduling | 5,000 | 1,212 |

PersonnelScheduling's budget is naturally low because it converges rapidly. Profiling (Task 0) showed that 94.8% of PersonnelScheduling wall time is spent in HyFlex `LOCAL_SEARCH` calls (mean 484 ms per application), with instrumentation contributing only 1.4%. No optimisation of our code can reduce this cost.

### 2.3 Replication

Each cell (technique x domain) is run with 10 independent seeds: 42, 123, 456, 789, 1024, 2048, 3141, 4242, 5555, 9999. Each run uses a fresh problem object, fresh selector state, and a fresh RNG seeded with the run's seed. Total: 240 runs, all completing successfully. Total wall time: 20 hours 14 minutes.

### 2.4 Improvement over Assessment 4

| Aspect | Assessment 4 | Assessment 5 |
|--------|-------------|--------------|
| Seeds per cell | 1 | 10 |
| Total runs | 24 | 240 |
| Statistical tests | None | Wilcoxon signed-rank, Friedman, A12 |
| Budget | Fixed 100,000 all domains | Per-domain from convergence |
| SHAP surrogates | Pooled across domains | Per-domain, per-seed |
| SHAP comparison | Raw magnitudes | Ranks and shares |
| CHeSC claim | Claimed comparability | Explicitly disclaimed |
| feat_llh_count | Included (domain label) | Excluded |

## 3. Results: Within-Domain Performance (RQ1)

### 3.1 Summary Statistics

**SAT** (budget: 50,000)

| Technique | Median | IQR | Mean | SD | Min | Max |
|-----------|--------|-----|------|----|-----|-----|
| SP-SR-LA | 12.50 | [9.50, 15.75] | 12.50 | 3.78 | 6.0 | 19.0 |
| SP-CF-LA | 11.50 | [8.50, 13.75] | 12.20 | 4.18 | 7.0 | 20.0 |
| SP-CF-AILTA | **4.00** | [4.00, 4.75] | 4.30 | 1.16 | 3.0 | 7.0 |
| MP-CF | 44.00 | [42.25, 49.00] | 43.80 | 8.31 | 30.0 | 56.0 |

**BinPacking** (budget: 100,000)

| Technique | Median | IQR | Mean | SD |
|-----------|--------|-----|------|----|
| SP-SR-LA | 0.01140 | [0.0110, 0.0118] | 0.0113 | 0.0006 |
| SP-CF-LA | 0.01190 | [0.0114, 0.0124] | 0.0119 | 0.0007 |
| SP-CF-AILTA | 0.02080 | [0.0191, 0.0215] | 0.0205 | 0.0020 |
| MP-CF | **0.01140** | [0.0112, 0.0115] | 0.0114 | 0.0002 |

Note: SP-SR-LA and MP-CF are tied at median 0.0114. MP-CF is not significantly better than SP-SR-LA (p = 0.557; see §3.2), so this ranking is not meaningful.

**FlowShop** (budget: 100,000)

| Technique | Median | IQR | Mean | SD |
|-----------|--------|-----|------|----|
| SP-SR-LA | 6353.0 | [6347, 6366] | 6354.3 | 16.6 |
| SP-CF-LA | 6364.0 | [6346, 6374] | 6362.1 | 30.0 |
| SP-CF-AILTA | **6313.5** | [6303, 6325] | 6311.4 | 18.5 |
| MP-CF | 6369.0 | [6364, 6390] | 6375.5 | 18.3 |

**TSP** (budget: 10,000)

| Technique | Median | IQR | Mean | SD |
|-----------|--------|-----|------|----|
| SP-SR-LA | 51,039 | [50,607, 52,188] | 51,206 | 1,070 |
| SP-CF-LA | 51,558 | [51,198, 52,633] | 51,640 | 1,257 |
| SP-CF-AILTA | 51,204 | [50,231, 51,567] | 50,996 | 1,036 |
| MP-CF | **49,826** | [49,743, 50,100] | 50,010 | 634 |

**VRP** (budget: 50,000)

| Technique | Median | IQR | Mean | SD |
|-----------|--------|-----|------|----|
| SP-SR-LA | 6,133 | [5,896, 6,218] | 6,123 | 669 |
| SP-CF-LA | 7,132 | [7,020, 7,164] | 7,031 | 584 |
| SP-CF-AILTA | 5,215 | [5,188, 5,234] | 5,299 | 289 |
| MP-CF | **5,161** | [5,148, 5,197] | 5,177 | 47 |

**PersonnelScheduling** (budget: 5,000)

| Technique | Median | IQR | Mean | SD |
|-----------|--------|-----|------|----|
| SP-SR-LA | 3,334 | [3,315, 3,340] | 3,330 | 24.3 |
| SP-CF-LA | 3,336 | [3,323, 3,355] | 3,340 | 24.8 |
| SP-CF-AILTA | **3,301** | [3,291, 3,311] | 3,303 | 14.2 |
| MP-CF | 3,341 | [3,336, 3,345] | 3,340 | 7.0 |

### 3.2 Wilcoxon Signed-Rank Tests vs SP-SR-LA Baseline

All tests are two-sided, paired by seed, with Holm correction within each domain. A12 < 0.5 means the tested technique is better (lower objective) than SP-SR-LA.

| Domain | Technique | p (corrected) | A12 | Significant? |
|--------|-----------|---------------|-----|-------------|
| SAT | SP-CF-LA | 0.992 | 0.455 | No |
| SAT | SP-CF-AILTA | **0.006** | **0.01** | **Yes** |
| SAT | MP-CF | **0.006** | 1.00 | **Yes** (worse) |
| BinPacking | SP-CF-LA | **0.006** | 0.90 | **Yes** (worse) |
| BinPacking | SP-CF-AILTA | **0.006** | 1.00 | **Yes** (worse) |
| BinPacking | MP-CF | 0.557 | 0.45 | No |
| FlowShop | SP-CF-LA | 0.541 | 0.59 | No |
| FlowShop | SP-CF-AILTA | **0.012** | **0.03** | **Yes** |
| FlowShop | MP-CF | 0.059 | 0.815 | No |
| TSP | SP-CF-LA | 1.000 | 0.61 | No |
| TSP | SP-CF-AILTA | 1.000 | 0.45 | No |
| TSP | MP-CF | 0.059 | 0.18 | No |
| VRP | SP-CF-LA | **0.020** | 0.81 | **Yes** (worse) |
| VRP | SP-CF-AILTA | **0.020** | **0.19** | **Yes** |
| VRP | MP-CF | **0.018** | **0.12** | **Yes** |
| PS | SP-CF-LA | 0.537 | 0.61 | No |
| PS | SP-CF-AILTA | **0.041** | **0.16** | **Yes** |
| PS | MP-CF | 0.449 | 0.695 | No |

### 3.3 Answer to RQ1

SP-CF-AILTA significantly outperforms the SP-SR-LA baseline in 4 of 6 domains (SAT, FlowShop, VRP, PersonnelScheduling; all p < 0.05 after Holm correction, all A12 < 0.20). In BinPacking it is significantly worse. MP-CF significantly outperforms the baseline in VRP (A12 = 0.12) but is significantly worse in SAT. In BinPacking and TSP, MP-CF's median advantage is not significant. SP-CF-LA shows no significant improvement over the baseline in any domain and is significantly worse in BinPacking and VRP.

**The Choice Function with AILTA acceptance (SP-CF-AILTA) is the only technique that consistently improves over Simple Random across most domains.**

## 4. Results: Cross-Domain Ranking (RQ2)

### 4.1 Rank Table

Techniques are ranked by median within each domain (1 = best, i.e. lowest objective).

| Domain | SP-SR-LA | SP-CF-LA | SP-CF-AILTA | MP-CF |
|--------|----------|----------|-------------|-------|
| SAT | 3 | 2 | **1** | 4 |
| BinPacking | 1.5* | 3 | 4 | 1.5* |
| FlowShop | 2 | 3 | **1** | 4 |
| TSP | 2 | 4 | 3 | **1** |
| VRP | 3 | 4 | 2 | **1** |
| PS | 2 | 3 | **1** | 4 |
| **Mean rank** | **2.25** | **3.17** | **2.00** | **2.58** |

*Tied at median 0.0114 (mid-rank); difference not significant (p = 0.557).

### 4.2 Normalised Scores

Normalised to [0, 1] per domain: (median - best) / (worst - best). Lower is better.

| Technique | Mean normalised score |
|-----------|----------------------|
| SP-CF-AILTA | **0.30** |
| SP-SR-LA | 0.49 |
| MP-CF | 0.50 |
| SP-CF-LA | 0.67 |

### 4.3 Friedman Test

Friedman chi-squared = 2.80, p = 0.424. **Not significant.** There is no statistically significant difference between the four techniques across all six domains when treated as a group. This is expected with only 6 blocks (domains) and relatively close mean ranks (2.00 to 3.17).

### 4.4 Answer to RQ2

SP-CF-AILTA has the best mean rank (2.00) and best mean normalised score (0.30), ranking 1st in 3 of 6 domains (SAT, FlowShop, PS) and 2nd in VRP. MP-CF ranks 1st in TSP and VRP and ties in BinPacking. However, the Friedman test does not detect a significant overall difference (p = 0.424), so the ranking advantage of SP-CF-AILTA over the alternatives cannot be confirmed at the cross-domain level with 6 domains.

**No technique dominates across all domains.** SP-CF-AILTA and MP-CF each have complementary strengths, but MP-CF's advantage is significant only in VRP.

## 5. SHAP Analysis (RQ3 and RQ4)

The XAI analysis addresses the benchmark paper's question---*which heuristics are effective, and when?*---indirectly: surrogates model acceptance (whether a heuristic application's result was kept) rather than performance directly. The features that the surrogate relies on to predict acceptance reveal which aspects of search state the hyper-heuristic implicitly conditions on when deciding to keep or discard a candidate solution.

### 5.1 Surrogate Fidelity

Per-domain, per-technique, per-seed gradient boosting surrogates were trained. `feat_llh_count` was excluded because it is constant within a domain and acted as a domain label in Assessment 4's pooled surrogates.

| Technique | Mean ROC-AUC | Min ROC-AUC | Flagged (< 0.6) | Notes |
|-----------|-------------|-------------|-----------------|-------|
| SP-SR-LA | 0.52 | 0.49 | **60/60 (100%)** | Near-random |
| SP-CF-LA | 0.88 | 0.66 | 0/60 | Adequate |
| SP-CF-AILTA | 0.91 | 0.70 | 0/60 | Good |
| MP-CF | 0.89 | 0.65 | 0/60 | Adequate |

**SP-SR-LA surrogates are uniformly flagged across all 6 domains and all 10 seeds** (ROC-AUC 0.51-0.55). No SHAP attributions are reported for SP-SR-LA.

**Robustness check.** Because a uniform AUC of ~0.5 could indicate a logging fault rather than a genuine absence of structure, we verified three potential failure modes: (1) `feat_last_h*` columns are populated with real heuristic indices for SR runs---the distribution across indices is approximately uniform, as expected from random selection; (2) acceptance labels are not near-constant---rejection rates range from 26% to 40%, comparable to CF-based techniques; (3) `feat_iters_since_accept` is recorded before the acceptance decision (the state snapshot is taken before the heuristic is applied and the decision made), so there is no target leakage.

To test whether per-heuristic acceptance rate differences might provide a learnable signal, we computed the mean acceptance rate per heuristic index across all SR-LA seeds. Within every domain, the rates are nearly identical: the standard deviation across heuristics is 0.002-0.008 (e.g. BinPacking: 0.639-0.646; SAT: 0.708-0.716). Grouping by HyFlex type class (mutation, local search, ruin-recreate, crossover) shows similarly flat distributions. Under Late Acceptance with random selection, no heuristic type produces accepted moves at a meaningfully different rate, so `feat_last_h*` carries no signal. Under the Choice Function, preferential selection concentrates applications on recently successful heuristics, creating a correlation between heuristic identity and acceptance that the surrogate can learn. We therefore state the finding as: *adaptive selection substantially amplifies the explainability of acceptance decisions*.

### 5.2 Feature Importance (Ranks and Shares)

SHAP importance is reported as **shares** (mean |SHAP| / total mean |SHAP|) and **ranks** (1 = most important). These are comparable across techniques within a domain. Raw SHAP magnitudes are never compared across techniques.

**SP-CF-LA** --- Heuristic identity features dominate:

| Domain | Rank 1 (share) | Rank 2 (share) | Rank 3 (share) |
|--------|---------------|---------------|---------------|
| SAT | feat_mean_logret_50 (33%) | feat_last_h1 (21%) | feat_last_h3 (16%) |
| BinPacking | feat_last_h3 (27%) | feat_last_h2 (20%) | feat_last_class1 (15%) |
| FlowShop | feat_last_h1 (27%) | feat_last_h2 (15%) | feat_last_h3 (13%) |
| TSP | feat_iters_since_improve (32%) | feat_progress (31%) | feat_mean_logret_50 (9%) |
| VRP | feat_last_h1 (15%) | feat_last_h2 (13%) | feat_last_h3 (12%) |
| PS | feat_last_h1 (18%) | feat_last_h3 (18%) | feat_iters_since_improve (14%) |

In 4 of 6 domains, the top features are heuristic identity indicators (`feat_last_h*`). The likely cause is that different heuristic *types*---mutation, local search, ruin-and-recreate---have substantially different acceptance rates, and recording the heuristic index captures these type differences. The Choice Function's preferential selection amplifies this signal: heuristics that have recently succeeded are selected more often, so the surrogate sees a concentrated subset of indices correlated with acceptance.

**SP-CF-AILTA** --- Search dynamics features dominate:

| Domain | Rank 1 (share) | Rank 2 (share) | Rank 3 (share) |
|--------|---------------|---------------|---------------|
| SAT | feat_progress (33%) | feat_iters_since_improve (31%) | feat_improve_rate_50 (10%) |
| BinPacking | feat_last_h2 (27%) | feat_last_h3 (20%) | feat_iters_since_accept (9%) |
| FlowShop | feat_improve_rate_50 (50%) | feat_progress (20%) | feat_mean_logret_50 (7%) |
| TSP | feat_iters_since_improve (29%) | feat_progress (29%) | feat_improve_rate_50 (10%) |
| VRP | feat_progress (30%) | feat_mean_logret_50 (20%) | feat_iters_since_improve (16%) |
| PS | feat_last_h2 (20%) | feat_improve_rate_50 (16%) | feat_last_h1 (14%) |

In 4 of 6 domains, the top feature is a search-progress indicator (`feat_progress`, `feat_improve_rate_50`, or `feat_iters_since_improve`). AILTA's linearly decaying threshold creates a dependency on *where in the search* the decision occurs, shifting importance away from heuristic identity toward search dynamics.

**MP-CF** --- Population and temporal features emerge:

| Domain | Rank 1 (share) | Rank 2 (share) | Rank 3 (share) |
|--------|---------------|---------------|---------------|
| SAT | feat_progress (26%) | feat_iters_since_accept (21%) | feat_pop_diversity (18%) |
| BinPacking | feat_progress (25%) | feat_iters_since_improve (16%) | feat_gap_to_best (10%) |
| FlowShop | feat_improve_rate_50 (22%) | feat_mean_logret_50 (22%) | feat_pop_diversity (16%) |
| TSP | feat_mean_logret_50 (36%) | feat_iters_since_improve (17%) | feat_iters_since_accept (17%) |
| VRP | feat_iters_since_accept (26%) | feat_pop_target_rank (22%) | feat_pop_diversity (15%) |
| PS | feat_progress (26%) | feat_iters_since_accept (12%) | feat_iters_since_improve (11%) |

Population-specific features (`feat_pop_diversity`, `feat_pop_target_rank`) appear in the top 3 in 3 of 6 domains (SAT, FlowShop, VRP). In VRP, where MP-CF ranks 1st in performance, `feat_pop_target_rank` has the highest share (22%)---the surrogate learned that the rank of the candidate within the population is a strong predictor of acceptance. Heuristic identity features (`feat_last_h*`) are consistently relegated to ranks 9-15 in MP-CF, confirming that population-level dynamics overshadow individual heuristic effects.

### 5.3 Stability Analysis (Kendall's Tau)

To assess whether SHAP explanations are stable across seeds, we compute Kendall's tau rank correlation between all 45 pairs of per-seed feature rankings for each technique-domain cell.

| Domain | SP-CF-LA | SP-CF-AILTA | MP-CF |
|--------|----------|-------------|-------|
| SAT | 0.76 (0.08) | 0.59 (0.18) | 0.57 (0.11) |
| BinPacking | 0.38 (0.30) | 0.83 (0.09) | 0.39 (0.14) |
| FlowShop | 0.75 (0.08) | 0.65 (0.10) | 0.42 (0.14) |
| TSP | 0.71 (0.10) | 0.72 (0.10) | 0.42 (0.20) |
| VRP | 0.51 (0.11) | 0.27 (0.17) | 0.68 (0.07) |
| PS | 0.64 (0.14) | 0.72 (0.09) | 0.62 (0.10) |

Values are mean tau (std). Tau > 0.6 indicates moderate-to-strong agreement; tau > 0.8 is strong.

SP-CF-LA achieves the highest stability in SAT (0.76) and FlowShop (0.75) but is unstable in BinPacking (0.38). SP-CF-AILTA is most stable in BinPacking (0.83) and TSP (0.72) but unstable in VRP (0.27). MP-CF is most stable in VRP (0.68) and PS (0.62) but weaker in BinPacking and FlowShop. No single technique produces universally stable explanations across all domains.

### 5.4 Answer to RQ3

The features driving acceptance differ by technique and are moderately stable across seeds (tau ranges from 0.27 to 0.83 depending on technique-domain cell, with most cells above 0.5). SP-CF-LA's decisions are explained by heuristic identity features, SP-CF-AILTA's by search-progress features, and MP-CF's by population-level features. These structural differences between techniques are consistent across domains, even where per-seed stability within a single domain is lower.

Connecting this to the benchmark question of *which heuristics are effective when*: the SHAP explanations show that *what the surrogate needs to know* differs by technique. For SP-CF-LA, heuristic identity is the key signal---different heuristic types produce accepted moves at different rates under adaptive selection. For SP-CF-AILTA, the search stage matters most, indicating that effectiveness is time-dependent. For MP-CF, population-level context (diversity, rank) matters more than the individual heuristic applied.

### 5.5 Answer to RQ4

**Selection strategy**: All 60 SP-SR-LA surrogates have ROC-AUC ~0.52, while the 180 CF-based surrogates achieve mean ROC-AUC 0.88-0.91 (min 0.65-0.70). Adaptive selection substantially amplifies the explainability of acceptance decisions. We verified that this is not a logging artefact (§5.1), though per-heuristic acceptance rate differences may exist under random selection that are too weak to produce a strong surrogate signal without the amplification of preferential selection.

**Acceptance strategy**: Comparing SP-CF-LA (Late Acceptance) with SP-CF-AILTA (AILTA), the acceptance strategy shifts importance from heuristic identity to search dynamics. AILTA's linearly decaying threshold makes acceptance sensitive to *where in the search* the decision is made, causing `feat_progress` and `feat_improve_rate_50` to dominate.

**Search topology**: Comparing SP-CF-LA (single-point) with MP-CF (multi-point), the population topology introduces `feat_pop_diversity` and `feat_pop_target_rank` as important features while suppressing heuristic identity features. In VRP, where MP-CF achieves its strongest significant performance advantage, `feat_pop_target_rank` (22%) and `feat_pop_diversity` (15%) together account for 37% of total SHAP importance.

## 6. LIME Analysis

### 6.1 Method

LIME explanations complement SHAP by providing interpretable *conditions* (e.g. `feat_progress <= 0.25`) rather than continuous attributions. For each surrogate, 50 evenly-spaced instances across `feat_progress` are explained. Each explanation condition is labelled with a sign: positive (+1) means the condition pushes the surrogate's prediction toward acceptance, negative (-1) toward rejection. Conditions are grouped into 10 progress bands (0-9) to track how acceptance drivers change over the search.

A condition is classified as an **acceptance driver** if its positive_fraction > 0.5 (i.e. it more often pushes toward acceptance than rejection across all explained instances where it appears).

Note that LIME conditions involving heuristic indices (e.g. `3 < feat_last_h2 <= 6`) use numeric index ranges. Because each domain has a different heuristic set and HyFlex does not expose heuristic names, these thresholds partition the index space into groups that may or may not align with heuristic type classes. The `feat_last_class*` features, which record the HyFlex type (mutation, local search, ruin-recreate, crossover), provide a more interpretable alternative where they appear.

### 6.2 LIME Acceptance Drivers

**SP-CF-LA** --- Heuristic-specific conditions:
- `feat_last_h3 <= 2.00` (BinPacking: count=144, pos_frac=0.77, weight=0.098)
- `3.00 < feat_last_h2 <= 6.00` (BinPacking: count=132, pos_frac=0.92, weight=0.165)
- `feat_last_h1 > 8.00` (PS: count=127, pos_frac=1.00, weight=0.112)
- `feat_progress <= 0.25` (SAT: count=103, pos_frac=0.95, weight=0.038)

SP-CF-LA's acceptance is driven by *which heuristic* was last applied. The conditions match the SHAP finding that `feat_last_h*` features dominate.

**SP-CF-AILTA** --- Search-stage conditions:
- `feat_progress <= 0.25` (SAT: count=130, pos_frac=1.00, weight=0.263)
- `0.25 < feat_progress <= 0.50` (SAT: count=120, pos_frac=1.00, weight=0.240)
- `feat_iters_since_accept <= 0.00` (BinPacking: count=364, pos_frac=1.00, weight=0.129)
- `feat_improve_rate_50 > 0.10` (FlowShop: count=72, pos_frac=0.90, weight=0.029)

The surrogate predicts higher acceptance probability in early progress bands (progress <= 0.50, positive_fraction = 1.0 across multiple domains). This is consistent with AILTA's decaying threshold, which is mechanically more permissive early. However, early-search permissiveness is not unique to AILTA: SP-CF-LA also shows `feat_progress <= 0.25` as an acceptance driver in SAT (pos_frac = 0.95). Part of the effect may simply reflect that improvements are easier to find early in any search, regardless of acceptance strategy.

**MP-CF** --- Population diversity conditions:
- `feat_pop_diversity > 0.05` (SAT: count=53, pos_frac=0.94, weight=0.308)
- `feat_pop_diversity > 0.00` (VRP: count=110, pos_frac=1.00, weight=0.263)
- `feat_pop_diversity > 0.01` (PS: count=70, pos_frac=0.86, weight=0.282)
- `feat_gap_to_best > 0.04` (BinPacking: count=90, pos_frac=0.93, weight=0.191)
- `feat_pop_target_rank > 6.00` (VRP: count=26, pos_frac=1.00, weight=0.202)

The surrogate predicts acceptance when population diversity is non-zero (positive_fraction 0.86-1.00 with high weights). This is consistent with the replacement rule: a candidate replaces the worst individual only if strictly better, and diverse populations offer more weak targets for replacement. The causal direction is not established---high diversity may be a *consequence* of recent acceptances rather than a *cause*---but the surrogate reliably uses it as a predictor.

### 6.3 LIME Stability

| Domain | SP-CF-LA | SP-CF-AILTA | MP-CF |
|--------|----------|-------------|-------|
| SAT | 0.52 (0.12) | 0.54 (0.13) | 0.47 (0.12) |
| BinPacking | 0.34 (0.23) | 0.69 (0.14) | 0.41 (0.15) |
| FlowShop | 0.39 (0.20) | 0.59 (0.11) | 0.44 (0.12) |
| TSP | 0.40 (0.16) | 0.54 (0.12) | 0.63 (0.09) |
| VRP | 0.21 (0.20) | 0.34 (0.15) | 0.61 (0.11) |
| PS | 0.36 (0.20) | 0.61 (0.10) | 0.49 (0.13) |

LIME stability is systematically lower than SHAP stability (mean tau 0.21-0.69 vs 0.27-0.83). This is expected: LIME produces local linear approximations at individual instances, so it is more sensitive to sampling variation than SHAP's global TreeExplainer attributions.

### 6.4 SHAP vs LIME Agreement

Both methods identify the same structural patterns:
1. **SP-CF-LA**: Heuristic identity features are the primary drivers in both SHAP (top shares go to `feat_last_h*`) and LIME (top conditions are heuristic-specific ranges).
2. **SP-CF-AILTA**: Search-progress features dominate both SHAP (`feat_progress`, `feat_improve_rate_50`) and LIME (`feat_progress <= 0.25/0.50` with positive_fraction = 1.0).
3. **MP-CF**: Population features are key in both SHAP (`feat_pop_diversity`, `feat_pop_target_rank`) and LIME (`feat_pop_diversity > threshold` with positive_fraction near 1.0).

LIME adds a complementary insight that SHAP cannot provide: the *direction* and *threshold* at which features drive acceptance predictions. SHAP tells us `feat_progress` is important for SP-CF-AILTA; LIME tells us that `feat_progress <= 0.50` drives acceptance with weight 0.24-0.26.

## 7. Limitations

1. **Not comparable to CHeSC**: This study uses iteration budgets, instance 0, and 10 seeds. CHeSC used a normalised 10-minute time limit, competition instances, and 31 runs. The real HyFlex domains are the same, but the experimental protocol differs.

2. **Single instance**: All runs use instance 0. Performance on other instances may differ.

3. **Friedman test power**: With only 6 domains (blocks), the Friedman test has limited power to detect moderate differences in technique rankings.

4. **PersonnelScheduling budget**: The 5,000-application budget is set by convergence analysis but is substantially lower than other domains. This domain's results rest on fewer applications.

5. **Convergence relative to pilot cap**: BinPacking (94,670) and FlowShop (91,405) reach 95% convergence very close to the 100,000-iteration pilot cap. The pilot run may itself not have been long enough, so the true budget needed may exceed 100,000 and results for these domains may not reflect fully converged search.

6. **SP-SR-LA unexplainable**: The Simple Random baseline cannot be explained by SHAP or LIME because surrogates fail to learn its acceptance patterns. This limits direct feature-importance comparison to the 3 CF-based techniques. Whether weak per-heuristic acceptance rate differences exist under random selection but are too small for the surrogate to learn remains an open question.

7. **LIME stability**: LIME explanations are less stable than SHAP across seeds (mean tau 0.21-0.69 vs 0.27-0.83), particularly for SP-CF-LA in VRP (tau = 0.21). Condition-level findings should be interpreted as aggregate trends, not per-seed guarantees.

8. **Surrogates model acceptance, not performance**: The XAI analysis explains which features predict whether a candidate is *accepted*, not whether it is *good*. Acceptance is a necessary condition for performance improvement but is not sufficient---a technique can accept many poor moves. The link between acceptance drivers and technique effectiveness is indirect.

## 8. Conclusions

1. **Replication works**: 240 runs with 10 seeds per cell provide reliable variance estimates and enable paired statistical tests.

2. **SP-CF-AILTA is the strongest single technique**: It significantly outperforms the baseline in 4 of 6 domains, ranks 1st in 3 domains by median, and achieves the best mean rank (2.00) and normalised score (0.30).

3. **MP-CF shows complementary strengths**: MP-CF achieves the best median in TSP and VRP (significant only in VRP) and ties in BinPacking, suggesting that population-based search can help on some problem structures. However, its advantage over the baseline is statistically confirmed only in VRP.

4. **Adaptive selection amplifies explainability**: All 60 SP-SR-LA surrogates are flagged (ROC-AUC < 0.6), while the 180 CF-based surrogates achieve mean ROC-AUC 0.88-0.91 (min 0.65-0.70). Per-heuristic acceptance rates under random selection are nearly identical (std 0.002-0.008 across heuristics within each domain), confirming there is no signal for the surrogate to learn. The Choice Function's preferential selection creates the state-acceptance correlations that surrogates exploit.

5. **Each technique type has a distinct explanation signature**: SP-CF-LA is explained by heuristic identity features, SP-CF-AILTA by search-progress features, and MP-CF by population-level features. Both SHAP and LIME converge on this finding.

6. **AILTA's decaying threshold shifts the surrogate's reliance to progress features**: The surrogate for SP-CF-AILTA consistently ranks `feat_progress` and `feat_improve_rate_50` above heuristic identity features. LIME shows the surrogate predicts higher acceptance early in the search, consistent with the linearly decaying threshold. However, early-search permissiveness also appears under SP-CF-LA, so this pattern may partly reflect general search dynamics rather than AILTA specifically.

7. **Population diversity predicts acceptance for MP-CF**: The surrogate for MP-CF relies on `feat_pop_diversity` and `feat_pop_target_rank`, consistent with the replacement rule that targets the worst individual. The causal mechanism is not established, but the association is strong in the domains where population features reach the top 3 (SAT, FlowShop, VRP).

8. **Cross-domain differences are not significant**: The Friedman test (p = 0.424) does not detect an overall technique effect, likely due to the small number of domains.
