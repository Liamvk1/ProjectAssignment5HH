# XAI-Driven Improvement Loop for Cross-Domain Selection Perturbative Hyper-Heuristics

## 1. Introduction

This report documents a closed-loop explainable AI (XAI) pipeline applied to selection perturbative hyper-heuristics (SPHH) on the HyFlex CHeSC benchmark. The pipeline: explains heuristic effectiveness from unconfounded traces, extracts deterministic selection masks from those explanations, implements masked variants in Java, runs experiments on a held-out instance, performs statistical comparison, and re-explains the variant behaviour.

Four research questions guide the study:

- **RQ1 (Understand):** Which heuristic types, in which search states and phases, produce improving moves in each domain?
- **RQ2 (Improve):** Do changes derived from the RQ1 explanations significantly improve SP-CF-AILTA and MP-CF over their unmodified versions?
- **RQ3 (Generalise):** Do the changes still help on a domain whose traces were not used to derive them?
- **RQ4 (Mechanism):** Did the improved variants change behaviour in the way the explanations predicted, and do they beat equally sized changes not chosen by XAI?

### Existing techniques (unmodified)

| Technique | Selection | Acceptance | Population |
|-----------|-----------|------------|------------|
| SP-SR-LA | Simple Random | Late Acceptance (L=50) | Single-point |
| SP-CF-LA | Modified Choice Function | Late Acceptance (L=50) | Single-point |
| SP-CF-AILTA | Modified Choice Function | Linear-decay AILTA | Single-point |
| MP-CF | Modified Choice Function | Binary tournament replacement | Population of 10 |

### Domains and budgets

| Domain | Budget (iterations) | Heuristic count |
|--------|-------------------|-----------------|
| SAT | 50,000 | 11 |
| BinPacking | 100,000 | 8 |
| FlowShop | 100,000 | 15 |
| TSP | 10,000 | 13 |
| VRP | 50,000 | 10 |
| PersonnelScheduling | 5,000 | 12 |

---

## 2. Phase 0: Data Inspection and Schema

**Input:** 240 Assessment 5 trace files (4 techniques x 6 domains x 10 seeds, instance 0).

Each trace row records one heuristic application with 19 fixed columns, 16 state feature columns (`feat_*`), and variable selection score columns (`score_*`). Full schema documented in `xai-sphh/docs/schema_map.md`.

Key design decisions:
- All `feat_*` columns are computed **before** the heuristic is applied (no leakage).
- `feat_llh_count` acts as a domain label and is excluded from all surrogates.
- Running-range normalisation (not full-run) prevents future information leaking into decision-time features.

---

## 3. Phase 1: Effectiveness Surrogates (RQ1)

### 3.1 Methodology

**Label:** `improved = 1` if `objective_after < objective_before` (strict improvement under minimisation).

**Features:** All pre-application `feat_*` (excluding `feat_llh_count`), plus the current heuristic encoded as:
- One-hot type class (`h_is_MUTATION`, `h_is_RUIN_RECREATE`, `h_is_LOCAL_SEARCH`, `h_is_CROSSOVER`)
- Within-domain index (`h_index`)

**Primary dataset:** SP-SR-LA traces. Under simple random selection the heuristic is independent of the search state, providing an unconfounded sample of heuristic effectiveness. Secondary surrogates were also trained on SP-CF-AILTA and MP-CF traces.

**Model:** GradientBoostingClassifier (100 trees, depth 4) with inverse-frequency class weighting. 5-fold stratified CV for fidelity assessment.

**Fidelity gate:** ROC-AUC >= 0.6 AND PR-AUC >= 2x positive base rate.

**SHAP:** TreeExplainer with conditional signed means for one-hot features — the SHAP value of `h_is_TYPE` is averaged only over instances where that type was actually applied (feature = 1). This correctly captures whether applying a specific type pushes the prediction toward or away from improvement.

### 3.2 Results

- **180 surrogates** trained (3 techniques x 6 domains x 10 seeds). All 180 passed the fidelity gate.
- ROC-AUC: 0.78 (VRP) to 0.99 (PersonnelScheduling).
- Stability: Kendall's tau of SHAP feature rankings across seed pairs: 0.49 to 0.85.

### 3.3 Effectiveness patterns

| Domain | Effective types (positive SHAP) | Ineffective types (negative SHAP, excluded) |
|--------|-------------------------------|----------------------------------------------|
| SAT | LOCAL_SEARCH, MUTATION | CROSSOVER, RUIN_RECREATE |
| BinPacking | RUIN_RECREATE, LOCAL_SEARCH | CROSSOVER, MUTATION |
| FlowShop | LOCAL_SEARCH, RUIN_RECREATE, MUTATION | None excluded |
| TSP | RUIN_RECREATE, LOCAL_SEARCH | CROSSOVER, MUTATION |
| VRP | MUTATION, LOCAL_SEARCH, RUIN_RECREATE | CROSSOVER |
| PersonnelScheduling | LOCAL_SEARCH, MUTATION, CROSSOVER | RUIN_RECREATE |

**Key insight:** LOCAL_SEARCH is the only type with consistently positive SHAP across all six domains. CROSSOVER is universally ineffective (near-zero observed improvement rate everywhere). MUTATION and RUIN_RECREATE are domain-dependent.

### 3.4 Output files

- `results/rq1/fidelity/fidelity_report.csv` — 180 surrogates, all passed
- `results/rq1/shap/shares_and_ranks.csv` — SHAP feature importance shares
- `results/rq1/shap/signed_shap_per_seed.csv` — Per-seed signed SHAP values
- `results/rq1/effectiveness_map/effectiveness_map.csv` — 720 rows (domain x type x band)
- `results/rq1/lime/lime_grid.csv` — LIME explanations
- `results/rq1/lime/condition_frequency.csv` — Aggregated LIME conditions
- `results/rq1/stability/kendall_tau.csv` — Cross-seed stability

---

## 4. Phase 2: Rule Extraction

### 4.1 Procedure

Rules are extracted by a fully deterministic procedure from the SP-SR-LA effectiveness map. No hand-tuned thresholds.

**Phase definitions** (from 10 progress bands):
- Early: bands 0-2 (progress 0.0 - 0.3)
- Middle: bands 3-6 (progress 0.3 - 0.7)
- Late: bands 7-9 (progress 0.7 - 1.0)

**Rule A (selection mask):** Exclude heuristic type T in phase P if:
1. Signed SHAP is negative in >= 8/10 seeds (consistent negative association with improvement)
2. Observed improvement rate < 0.5x the domain-phase mean (model-free confirmation)
3. At least one type remains allowed

### 4.2 Variants

| Variant | Suffix | Description |
|---------|--------|-------------|
| In-domain XAI | `-XAI` | Rules from the target domain's own effectiveness map |
| Cross-domain LODO | `-XAI-LODO` | Leave-one-domain-out majority vote across 5 other domains |
| Random control | `-RAND` | Same exclusion count as XAI, types chosen randomly (seed 12345) |
| Statistics control | `-STAT` | Exclusions by observed rate only, no surrogate/SHAP |

### 4.3 Exclusion summary

| Domain | Phase | XAI excluded | LODO excluded |
|--------|-------|-------------|---------------|
| SAT | early | CROSSOVER, RUIN_RECREATE | CROSSOVER |
| SAT | middle | CROSSOVER, RUIN_RECREATE | CROSSOVER |
| SAT | late | none | CROSSOVER |
| BinPacking | early | CROSSOVER, MUTATION | CROSSOVER |
| BinPacking | middle | CROSSOVER, MUTATION | CROSSOVER |
| BinPacking | late | CROSSOVER, MUTATION | none |
| FlowShop | all | none | CROSSOVER |
| TSP | early | CROSSOVER, MUTATION | CROSSOVER |
| TSP | middle | CROSSOVER, MUTATION | CROSSOVER |
| TSP | late | CROSSOVER | none |
| VRP | all | CROSSOVER | CROSSOVER (early/mid), none (late) |
| PersonnelScheduling | all | RUIN_RECREATE | CROSSOVER |

### 4.4 Output files

- `xai-sphh/rules/` — 48 JSON rule files across 8 variant directories
- `xai-sphh/rules/rules_summary.csv` — All exclusions in tabular form
- `xai-sphh/docs/rule_extraction.md` — Full deterministic procedure

---

## 5. Phase 3: Java Implementation

### 5.1 Architecture

The selection mask is implemented as a **decorator pattern** around the existing `SelectionStrategy` interface:

1. **`SelectionMask`** — Loads JSON rules, provides `isAllowed(heuristicIndex, budgetProgress)`. Three phases determined by progress thresholds (0.3, 0.7).

2. **`MaskedSelectionStrategy`** — Wraps `ChoiceFunction` (or `SimpleRandom`). The delegate computes scores for all heuristics as normal; the decorator overrides selection to pick the highest-scoring allowed heuristic. CF scores, phi updates, and f1/f2/f3 bookkeeping continue unchanged for all heuristics.

3. **`ExperimentRunner`** extended — Recognises XAI suffixes (`-XAI`, `-XAI-LODO`, `-RAND`, `-STAT`), strips them to find the base technique, loads `rules/<technique>/<domain>.json`, and wraps the selector.

4. **Trace extensions** — `feat_mask_active` and `feat_allowed_set_size` appended to the feature map when a mask is active.

5. **`Main.java`** modified — Accepts multiple config files in one JVM invocation, eliminating Gradle startup overhead.

### 5.2 Testing

- 6 new tests in `SelectionMaskTest.java`: phase boundaries, mask exclusions, JSON parsing, Rule B parsing, end-to-end masked selection
- All 32 tests pass (26 original + 6 new)
- Build: `./gradlew build` — BUILD SUCCESSFUL

### 5.3 New/modified files

- `java/src/main/java/za/ac/up/cos790/selection/SelectionMask.java` (new)
- `java/src/main/java/za/ac/up/cos790/selection/MaskedSelectionStrategy.java` (new)
- `java/src/main/java/za/ac/up/cos790/experiment/ExperimentRunner.java` (modified)
- `java/src/main/java/za/ac/up/cos790/hyperheuristic/HyperHeuristicBase.java` (modified)
- `java/src/main/java/za/ac/up/cos790/hyperheuristic/multipoint/MultiPointHyperHeuristic.java` (modified)
- `java/src/main/java/za/ac/up/cos790/Main.java` (modified)
- `java/src/test/java/za/ac/up/cos790/SelectionMaskTest.java` (new)

---

## 6. Phase 4: Experiments

### 6.1 Design

**Experiment matrix:** 2 base techniques x 5 variants x 6 domains x 10 seeds x 1 held-out instance = 600 runs.

- **Instance:** 1 (held-out; instance 0 was used for Assessment 5)
- **Seeds:** {11, 22, 33, 44, 55, 66, 77, 88, 99, 111}
- **Budget:** Per-domain iteration budgets (same as Assessment 5)

### 6.2 Execution

Initial sequential runner (`run_phase4_experiments.sh`) was too slow (~4 min/run with Gradle overhead). Replaced with parallel runner (`run_phase4_fast.sh`):
- Single JVM per worker (no Gradle startup per run)
- 6 parallel workers across 12 CPU cores
- Resumable (skips existing traces)

### 6.3 Completion

| Variant group | Completed | Total | Status |
|--------------|-----------|-------|--------|
| SP-CF-AILTA (all 5 variants) | 300 | 300 | Complete |
| MP-CF (base only) | 60 | 60 | Complete |
| MP-CF-XAI | 20 | 60 | Partial |
| MP-CF-XAI-LODO, RAND, STAT | 0 | 180 | Not started |
| **Total** | **380** | **600** | |

PersonnelScheduling was the computational bottleneck (~25 minutes wall time per 5,000-iteration run).

### 6.4 Output files

- `results/rq2/traces/` — 380 trace CSVs
- `config/phase4/` — 600 YAML config files
- `scripts/run_phase4_fast.sh` — Parallel runner script

---

## 7. Phase 5: Statistical Analysis (RQ2, RQ3, RQ4)

### 7.1 Methodology

- **Final objective:** `best_so_far` from the last row of each trace
- **Wilcoxon signed-rank tests:** Paired by seed, two-sided, with Holm-Bonferroni correction within each base-technique x domain group
- **Vargha-Delaney A12:** Effect size. A12 < 0.5 means the first variant is better (lower objective). Magnitudes: negligible (<0.56), small (<0.64), medium (<0.71), large (>=0.71)
- **Friedman test:** Across all 5 variants using median per domain as the observation

### 7.2 RQ2: XAI vs BASE

| Domain | Median BASE | Median XAI | A12 | Effect | p_corr | Sig |
|--------|------------|------------|-----|--------|--------|-----|
| SAT | 23.0 | 22.0 | 0.275 | large | 0.273 | no |
| BinPacking | 0.0170 | 0.0163 | 0.110 | large | 0.020 | **yes** |
| FlowShop | 6279.5 | 6283.0 | 0.610 | small | 0.580 | no |
| TSP | 117,602 | 117,336 | 0.540 | negl. | 1.000 | no |
| VRP | 20,677 | 20,686 | 0.570 | small | 1.000 | no |
| PersonnelScheduling | 2,312 | 3,028 | 0.880 | large | 0.109 | no |

**Answer:** XAI significantly improves BinPacking (p=0.020, A12=0.11, large effect). Trends favour XAI on SAT (large effect, not significant). XAI harms PersonnelScheduling (large effect, not significant after correction). No single variant dominates across domains (Friedman p=0.80).

### 7.3 RQ3: LODO generalisation

**Cross-domain ranks (by median, 1=best):**

| Domain | BASE | XAI | LODO | RAND | STAT |
|--------|------|-----|------|------|------|
| SAT | 4.0 | 2.5 | 2.5 | 5.0 | 1.0 |
| BinPacking | 3.0 | 1.0 | 2.0 | 5.0 | 4.0 |
| FlowShop | 3.0 | 4.0 | 1.0 | 2.0 | 5.0 |
| TSP | 4.0 | 3.0 | 5.0 | 2.0 | 1.0 |
| VRP | 2.0 | 4.0 | 1.0 | 3.0 | 5.0 |
| PersonnelScheduling | 1.0 | 5.0 | 3.0 | 4.0 | 2.0 |
| **Mean rank** | **2.83** | **3.25** | **2.42** | **3.50** | **3.00** |

**Answer:** LODO achieves the best mean Friedman rank (2.42). Its conservative strategy (exclude only CROSSOVER via majority vote) avoids domain-specific mistakes. LODO significantly outperforms XAI on FlowShop (p=0.049, A12=0.11). However, domain-specific XAI significantly outperforms LODO on BinPacking (p=0.010, A12=0.84). This is the bias-variance trade-off: LODO has lower variance but misses domain-specific signal.

### 7.4 RQ4: XAI vs controls

**Significant results (Holm-corrected p < 0.05):**

| Domain | Comparison | A12 | p_corr | Winner |
|--------|-----------|-----|--------|--------|
| BinPacking | XAI vs RAND | 0.000 | 0.010 | XAI |
| BinPacking | XAI vs STAT | 0.000 | 0.010 | XAI |
| PersonnelScheduling | XAI vs STAT | 0.850 | 0.010 | STAT |

**Answer:** On BinPacking, XAI significantly outperforms both controls (A12=0.00), confirming the SHAP-guided exclusions provide signal beyond mere pool reduction. On PersonnelScheduling, XAI is less destructive than STAT but both are worse than BASE.

### 7.5 Output files

- `results/rq2/statistics/per_domain_summary.csv`
- `results/rq2/statistics/wilcoxon_tests.csv` — 30 pairwise tests
- `results/rq2/statistics/friedman_tests.csv`
- `results/rq2/statistics/cross_domain_ranks.csv`
- `results/rq2/figures/boxplots_SP-CF-AILTA.png`
- `results/rq2/figures/boxplots_MP-CF.png`

---

## 8. Phase 6: Re-Explanation (RQ4 Mechanism)

### 8.1 Surrogate retraining

60 effectiveness surrogates retrained on SP-CF-AILTA-XAI traces (6 domains x 10 seeds). All passed fidelity:
- ROC-AUC: 0.73 (TSP) to 0.99 (PersonnelScheduling, TSP seed 111)
- The surrogates confirm the XAI variant traces contain learnable effectiveness signal.

### 8.2 Behavioural shifts

| Domain | Phase | BASE impr rate | XAI impr rate | BASE wasted | XAI wasted |
|--------|-------|---------------|---------------|-------------|------------|
| BinPacking | early | 0.190 | 0.307 (+62%) | 0.229 | 0.001 |
| BinPacking | middle | 0.153 | 0.252 (+65%) | 0.240 | 0.003 |
| BinPacking | late | 0.045 | 0.090 (+100%) | 0.331 | 0.112 |
| SAT | early | 0.101 | 0.129 (+28%) | 0.002 | 0.000 |
| SAT | middle | 0.089 | 0.114 (+28%) | 0.005 | 0.005 |
| FlowShop | early | 0.106 | 0.125 (+18%) | 0.006 | 0.007 |
| PersonnelScheduling | early | 0.016 | 0.009 (-44%) | 0.118 | 0.092 |
| PersonnelScheduling | middle | 0.002 | 0.000 (-100%) | 0.144 | 0.105 |

**BinPacking:** The mask concentrates applications on RUIN_RECREATE and LOCAL_SEARCH. Improvement rate nearly doubles in early/middle phases. Wasted applications drop from 23% to near 0%. This explains the significant performance improvement.

**PersonnelScheduling:** Excluding RUIN_RECREATE eliminates improvement entirely in middle/late phases. The type serves as a diversification operator under CF selection despite having negative SHAP under random selection.

### 8.3 SHAP shift analysis

| Domain | Type | Phase 1 SHAP | XAI variant SHAP | Shift | Was excluded? |
|--------|------|-------------|-----------------|-------|--------------|
| SAT | CROSSOVER | -0.543 | 0.000 | +0.543 | Yes |
| SAT | RUIN_RECREATE | -1.040 | 0.000 | +1.040 | Yes |
| SAT | LOCAL_SEARCH | +0.292 | +0.234 | -0.057 | No |
| BinPacking | CROSSOVER | -0.545 | 0.000 | +0.545 | Yes |
| BinPacking | MUTATION | -0.502 | 0.000 | +0.502 | Yes |
| BinPacking | LOCAL_SEARCH | +1.234 | +0.030 | -1.204 | No |
| PersonnelScheduling | RUIN_RECREATE | -0.109 | 0.000 | +0.109 | Yes |
| PersonnelScheduling | LOCAL_SEARCH | +0.269 | 0.000 | -0.269 | No |

Excluded types show SHAP of 0.0 in the XAI variant (they are never applied, so no SHAP contribution). The remaining types' SHAP values shift as the surrogate adapts to the new heuristic distribution.

### 8.4 Mismatch detection

| Domain | Perf improved? | Significant? | Behaviour changed? | Mismatch? |
|--------|---------------|-------------|-------------------|-----------|
| SAT | Yes | No | No | Yes: performance without behaviour |
| BinPacking | Yes | Yes | No (SHAP direction) | Yes: mechanism differs from prediction |
| FlowShop | No | No | No | None |
| TSP | No | No | No | None |
| VRP | No | No | No | None |
| PersonnelScheduling | No | No | No | None |

**SAT mismatch:** Performance trends better (A12=0.275) but the excluded types (CROSSOVER, RUIN_RECREATE) were already rarely selected by CF, so the mask changed little. The improvement may be seed variance.

**BinPacking mismatch:** Performance significantly improved but the SHAP shift direction was unexpected. The behavioural metrics tell the real story: the mask concentrated applications on effective types, dramatically increasing the improvement rate. The SHAP "mismatch" is an artefact of comparing surrogates trained on different heuristic distributions.

### 8.5 Output files

- `results/rq4_mechanism/behavioural/per_seed_metrics.csv`
- `results/rq4_mechanism/behavioural/aggregate_metrics.csv`
- `results/rq4_mechanism/behavioural/mismatch_flags.csv`
- `results/rq4_mechanism/shap_shift/shap_shift.csv`
- `results/rq4_mechanism/fidelity/xai_variant_fidelity.csv`

---

## 9. MP-CF Results (Partial)

Only MP-CF base (60 runs) and MP-CF-XAI (20 runs across 6 domains with 2-4 seeds each) completed. Preliminary observations:

| Domain | MP-CF median | MP-CF-XAI median | Better? |
|--------|-------------|-----------------|---------|
| SAT | 48.0 | 47.0 | XAI |
| BinPacking | 0.0081 | 0.0118 | BASE |
| FlowShop | 6313.0 | 6323.0 | BASE |
| TSP | 114,190 | 115,683 | BASE |
| VRP | 21,174 | 22,703 | BASE |
| PersonnelScheduling | 2,280 | 2,180 | XAI |

These results are from too few seeds to draw statistical conclusions. MP-CF-RAND, MP-CF-STAT, and MP-CF-XAI-LODO did not complete due to time constraints.

---

## 10. Conclusions

### What worked

1. **BinPacking:** XAI-guided selection masking produces a statistically significant improvement (p=0.020, large effect A12=0.11) by excluding CROSSOVER and MUTATION, concentrating applications on the effective RUIN_RECREATE and LOCAL_SEARCH types. This doubles the early-phase improvement rate and virtually eliminates wasted applications.

2. **LODO generalisation:** The cross-domain majority-vote approach achieves the best mean rank across all domains (2.42), demonstrating that XAI explanations can transfer across domains when aggregated conservatively.

3. **Controls validation:** On BinPacking, XAI outperforms both random (RAND) and statistics-only (STAT) controls with A12=0.00, confirming the SHAP-based signal provides genuine insight beyond simple improvement rate statistics or arbitrary pool reduction.

4. **Surrogate quality:** All 240 surrogates (180 Phase 1 + 60 Phase 6) passed fidelity gates, demonstrating that effectiveness prediction is a learnable task across all domains.

### What did not work

1. **PersonnelScheduling:** The XAI mask worsens performance by excluding RUIN_RECREATE, which serves as a diversification operator under CF selection despite having negative SHAP under random selection. This reveals a fundamental limitation: effectiveness under unconfounded random selection does not always transfer to effectiveness under intelligent selection.

2. **No universal improvement:** The Friedman test across all 6 domains is not significant (p=0.80). The XAI mask helps on some domains and hurts on others — domain-specific tuning cannot be replaced by a single strategy.

3. **FlowShop:** No types excluded because all pass the fidelity threshold, making the XAI and BASE variants identical.

### Key insight

The transfer gap between random and intelligent selection is the most important finding. Under random selection, every type gets equal exposure, and SHAP captures marginal effectiveness. Under CF selection, the selector already avoids poor heuristics adaptively — the mask may exclude types that CF would rarely choose anyway (SAT), or may remove diversification operators that CF depends on (PersonnelScheduling). Future work should train surrogates on the target technique's own traces, not just the unconfounded baseline.

---

## 11. Limitations

1. **Single held-out instance:** All Phase 4 experiments used instance 1 only. Results may not generalise to other instances within each domain.
2. **Friedman power:** With 6 domains and 5 variants, the Friedman test has limited statistical power. The non-significant result does not prove equivalence.
3. **PersonnelScheduling budget:** Only 5,000 iterations but each takes ~25 minutes wall time, making it the computational bottleneck that prevented MP-CF completion.
4. **MP-CF incomplete:** Only 80/300 MP-CF experiments completed. The multi-point analysis is inconclusive.
5. **CHeSC protocol not followed:** We used iteration budgets for reproducibility rather than the competition's 10-minute wall-clock runs.
6. **Transfer assumption:** Rules derived from SP-SR-LA traces (random selection) applied to SP-CF-AILTA (CF selection). The PersonnelScheduling result demonstrates this transfer is not always valid.
7. **No Rule B implementation:** Rule B (reheat/diversity triggers extracted from LIME) was not implemented in Java due to time constraints.
8. **Single base technique fully tested:** Only SP-CF-AILTA has complete statistical analysis across all 5 variants.

---

## 12. File Index

### Scripts

| Script | Purpose |
|--------|---------|
| `scripts/regenerate_a5_traces.sh` | Regenerate 240 Assessment 5 traces |
| `analysis/effectiveness/build_surrogates.py` | Phase 1: Train 180 effectiveness surrogates |
| `analysis/effectiveness/extract_rules.py` | Phase 2: Extract selection mask rules |
| `scripts/run_phase4_fast.sh` | Phase 4: Parallel experiment runner (6 workers) |
| `scripts/phase5_statistics.py` | Phase 5: Wilcoxon, Friedman, A12 analysis |
| `scripts/phase6_reexplain.py` | Phase 6: Re-explanation and mismatch detection |

### Java source (new/modified for XAI variants)

| File | Purpose |
|------|---------|
| `selection/SelectionMask.java` | Phase-dependent heuristic mask from JSON rules |
| `selection/MaskedSelectionStrategy.java` | Decorator restricting selection to allowed heuristics |
| `experiment/ExperimentRunner.java` | Extended for XAI variant technique names |
| `hyperheuristic/HyperHeuristicBase.java` | Mask feature logging in traces |
| `Main.java` | Multi-config batch execution |

### Results

| Directory | Contents |
|-----------|----------|
| `results/a5/traces/` | 240 Assessment 5 trace CSVs |
| `results/rq1/` | Phase 1 surrogates: fidelity, SHAP, LIME, effectiveness map, stability |
| `results/rq2/traces/` | 380 Phase 4 trace CSVs |
| `results/rq2/statistics/` | Phase 5 tables: summary, Wilcoxon, Friedman, ranks |
| `results/rq2/figures/` | Box plots per base technique |
| `results/rq4_mechanism/` | Phase 6: behavioural metrics, SHAP shift, mismatch flags |
| `rules/` | 48 JSON rule files + summary CSV |

### Documentation

| File | Contents |
|------|----------|
| `docs/schema_map.md` | Trace column definitions |
| `docs/rule_extraction.md` | Deterministic rule extraction procedure |
| `docs/results_summary.md` | Condensed results per RQ |
| `XAI_IMPROVEMENT_REPORT.md` | This document |
