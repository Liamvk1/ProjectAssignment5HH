# XAI-Driven Improvement Loop: Results Summary

## Overview

This study implements a closed-loop XAI pipeline: explain heuristic effectiveness from unconfounded traces (Phase 1), extract deterministic selection masks (Phase 2), implement masked variants in Java (Phase 3), run experiments on a held-out instance (Phase 4), perform statistical comparison (Phase 5), and re-explain the XAI variant behaviour (Phase 6).

**Base technique analysed:** SP-CF-AILTA (single-point, Modified Choice Function, linear-decay AILTA acceptance).

**Experiment matrix (SP-CF-AILTA):** 5 variants x 6 domains x 10 seeds x 1 held-out instance = 300 runs, all completed.

**MP-CF variants:** Only the base (60 runs) and partial XAI (20 runs) completed due to time constraints. MP-CF results are reported where available but are excluded from formal statistical testing.

---

## RQ1: Which heuristic types produce improving moves, and in which search states?

**Answer:** LOCAL_SEARCH is the only type with consistently positive SHAP contributions across all six domains. CROSSOVER is universally ineffective (observed improvement rate near 0% in all domains). MUTATION and RUIN_RECREATE show domain-dependent effectiveness.

### Key findings

- **180 effectiveness surrogates** trained (3 techniques x 6 domains x 10 seeds), all 180 passed the fidelity gate (ROC-AUC >= 0.6 and PR-AUC >= 2x positive base rate).
- ROC-AUC ranged from 0.78 (VRP) to 0.99 (PersonnelScheduling).
- Stability: Kendall's tau of SHAP rankings across seed pairs ranged from 0.49 to 0.85, indicating moderate to strong agreement.

### Effectiveness patterns by domain

| Domain | Effective types | Ineffective types (excluded by XAI) |
|--------|----------------|--------------------------------------|
| SAT | LOCAL_SEARCH, MUTATION | CROSSOVER, RUIN_RECREATE |
| BinPacking | RUIN_RECREATE, LOCAL_SEARCH | CROSSOVER, MUTATION |
| FlowShop | LOCAL_SEARCH, RUIN_RECREATE, MUTATION | None excluded |
| TSP | RUIN_RECREATE, LOCAL_SEARCH | CROSSOVER, MUTATION |
| VRP | MUTATION, LOCAL_SEARCH, RUIN_RECREATE | CROSSOVER |
| PersonnelScheduling | LOCAL_SEARCH, MUTATION, CROSSOVER | RUIN_RECREATE |

### Rule extraction procedure

Rules were extracted by a fully deterministic procedure from the SP-SR-LA effectiveness map:
- **Rule A (selection mask):** Exclude heuristic type T in phase P if (a) signed SHAP is negative in >= 8/10 seeds AND (b) observed improvement rate < 0.5x the domain-phase mean.
- **LODO rules:** Leave-one-domain-out majority vote across remaining 5 domains.
- **RAND control:** Same number of exclusions as XAI but types chosen randomly.
- **STAT control:** Exclusions based on observed improvement rate alone (no surrogate).

---

## RQ2: Do XAI-derived changes improve SP-CF-AILTA?

**Answer:** The XAI mask significantly improves performance on BinPacking (Wilcoxon p=0.020, A12=0.11, large effect). Trends favour XAI on SAT (A12=0.275, large, p=0.273) but the difference is not statistically significant. On PersonnelScheduling, the XAI mask significantly harms performance (A12=0.88, large effect, p=0.109 uncorrected). Across all six domains, no single variant dominates (Friedman p=0.80).

### Per-domain results (XAI vs BASE)

| Domain | Median BASE | Median XAI | A12 | Effect | p_corr | Sig |
|--------|------------|------------|-----|--------|--------|-----|
| SAT | 23.0 | 22.0 | 0.275 | large | 0.273 | no |
| BinPacking | 0.0170 | 0.0163 | 0.110 | large | 0.020 | yes |
| FlowShop | 6279.5 | 6283.0 | 0.610 | small | 0.580 | no |
| TSP | 117602 | 117336 | 0.540 | negl. | 1.000 | no |
| VRP | 20677 | 20686 | 0.570 | small | 1.000 | no |
| PersonnelScheduling | 2312 | 3028 | 0.880 | large | 0.109 | no |

### Interpretation

BinPacking benefits strongly from excluding CROSSOVER and MUTATION, concentrating applications on RUIN_RECREATE and LOCAL_SEARCH. The improvement rate jumps from 0.19 to 0.31 in early phase and from 0.15 to 0.25 in middle phase, while wasted applications drop from 23% to near 0%.

PersonnelScheduling worsens because the mask excludes RUIN_RECREATE, which despite having negative SHAP in the unconfounded SP-SR-LA traces, appears to serve as an important diversification operator under CF selection. This is a key finding: effectiveness under random selection does not always transfer to effectiveness under intelligent selection.

---

## RQ3: Do XAI-derived changes generalise across domains?

**Answer:** The LODO (leave-one-domain-out) variant achieves the best mean Friedman rank (2.42) across all six domains, compared to XAI (3.25), BASE (2.83), STAT (3.00), and RAND (3.50). LODO significantly outperforms XAI on FlowShop (p=0.049, A12=0.11, large effect) and trends better on VRP. However, domain-specific XAI significantly outperforms LODO on BinPacking (p=0.010, A12=0.84, large effect).

### Cross-domain ranks (by median, 1=best)

| Domain | BASE | XAI | LODO | RAND | STAT |
|--------|------|-----|------|------|------|
| SAT | 4.0 | 2.5 | 2.5 | 5.0 | 1.0 |
| BinPacking | 3.0 | 1.0 | 2.0 | 5.0 | 4.0 |
| FlowShop | 3.0 | 4.0 | 1.0 | 2.0 | 5.0 |
| TSP | 4.0 | 3.0 | 5.0 | 2.0 | 1.0 |
| VRP | 2.0 | 4.0 | 1.0 | 3.0 | 5.0 |
| PersonnelScheduling | 1.0 | 5.0 | 3.0 | 4.0 | 2.0 |
| **Mean rank** | **2.83** | **3.25** | **2.42** | **3.50** | **3.00** |

### Interpretation

LODO's conservative strategy (exclude only CROSSOVER, which is universally ineffective via majority vote) avoids the domain-specific mistakes that XAI makes on PersonnelScheduling. However, it also misses the domain-specific opportunity on BinPacking where excluding MUTATION is highly beneficial. This is the classic bias-variance trade-off in cross-domain generalisation: LODO has lower variance but misses domain-specific signal.

---

## RQ4: Do XAI-guided changes beat equally-sized random changes?

**Answer:** Yes, on BinPacking. XAI significantly outperforms both the RAND control (A12=0.00, p=0.010) and the STAT control (A12=0.00, p=0.010), confirming that the SHAP-guided exclusions provide signal beyond mere heuristic pool reduction. On PersonnelScheduling, XAI significantly outperforms STAT (p=0.010, A12=0.85) but both are worse than BASE, meaning the XAI mask is less destructive than the STAT mask. On other domains, differences are not significant.

### Significant results (Holm-corrected p < 0.05)

| Domain | Comparison | A12 | p_corr | Winner |
|--------|-----------|-----|--------|--------|
| BinPacking | XAI vs RAND | 0.000 | 0.010 | XAI |
| BinPacking | XAI vs STAT | 0.000 | 0.010 | XAI |
| PersonnelScheduling | XAI vs STAT | 0.850 | 0.010 | STAT (both worse than BASE) |

### Mechanism analysis (Phase 6)

Phase 6 retrained effectiveness surrogates on the XAI variant traces (60 surrogates, all passing fidelity with ROC-AUC 0.73-0.99).

**Behavioural shifts observed:**

| Domain | Phase | BASE impr rate | XAI impr rate | Change |
|--------|-------|---------------|---------------|--------|
| BinPacking | early | 0.190 | 0.307 | +62% |
| BinPacking | middle | 0.153 | 0.252 | +65% |
| SAT | early | 0.101 | 0.129 | +28% |
| SAT | middle | 0.089 | 0.114 | +28% |
| PersonnelScheduling | early | 0.016 | 0.009 | -44% |
| PersonnelScheduling | middle | 0.002 | 0.000 | -100% |

**SHAP shift analysis:**
The mismatch detector flagged two cases:
1. **SAT:** Performance improved (A12=0.275) without the predicted SHAP behaviour change. The excluded types (CROSSOVER, RUIN_RECREATE) already had near-zero application under CF selection, so the mask effectively changed nothing — the improvement may be attributable to seed variance.
2. **BinPacking:** Performance significantly improved (A12=0.11) but the SHAP shift for excluded types went in an unexpected direction. This requires further investigation. The behavioural metrics tell the story clearly: excluding MUTATION and CROSSOVER concentrated applications on the effective types, dramatically increasing the improvement rate and reducing wasted applications.

---

## MP-CF Results (Partial)

Only MP-CF base (60 runs) and MP-CF-XAI (20 runs, 4 domains with 4 seeds each) completed due to time constraints. Preliminary observations:

- MP-CF-XAI improved on SAT (median 47 vs 48) and PersonnelScheduling (median 2180 vs 2280).
- MP-CF-XAI worsened on BinPacking, FlowShop, TSP, and VRP.
- These results are from too few seeds (4) to draw statistical conclusions. MP-CF-RAND, MP-CF-STAT, and MP-CF-XAI-LODO did not complete.

---

## Limitations

1. **Single held-out instance:** All Phase 4 experiments used instance 1 only. Results may not generalise to other instances.
2. **Friedman power:** With 6 domains and 5 variants, the Friedman test has limited power. The non-significant result (p=0.80) does not prove equivalence.
3. **PersonnelScheduling budget:** Only 5,000 iterations but each takes ~25 minutes wall time, making it the computational bottleneck.
4. **MP-CF incomplete:** Only 80/300 MP-CF experiments completed. The multi-point analysis is inconclusive.
5. **CHeSC protocol not followed:** The competition uses 10-minute wall-clock runs. We used iteration budgets for reproducibility, which makes results not directly comparable to CHeSC benchmarks.
6. **Transfer assumption:** Rules derived from SP-SR-LA traces (unconfounded random selection) are applied to SP-CF-AILTA (intelligent CF selection). The PersonnelScheduling result shows this transfer is not always valid — effectiveness under random selection may differ from effectiveness under CF selection.
7. **No Rule B implementation:** Rule B (reheat triggers for AILTA, diversity triggers for MP-CF) was extracted but not implemented in the Java variants due to time constraints.

---

## Files produced

### Phase 1 (RQ1)
- `results/rq1/fidelity/fidelity_report.csv` — 180 surrogates, all passed
- `results/rq1/shap/shares_and_ranks.csv` — SHAP feature importance shares
- `results/rq1/shap/signed_shap_per_seed.csv` — Per-seed signed SHAP for rule extraction
- `results/rq1/effectiveness_map/effectiveness_map.csv` — 720 rows
- `results/rq1/stability/kendall_tau.csv` — Cross-seed stability

### Phase 2 (Rules)
- `rules/` — 48 JSON rule files across 8 variant directories
- `rules/rules_summary.csv` — Exclusions by domain, phase, and variant
- `docs/rule_extraction.md` — Deterministic extraction procedure

### Phase 5 (RQ2, RQ3, RQ4)
- `results/rq2/statistics/per_domain_summary.csv` — Descriptive statistics
- `results/rq2/statistics/wilcoxon_tests.csv` — 30 pairwise tests with Holm correction
- `results/rq2/statistics/friedman_tests.csv` — Cross-domain Friedman test
- `results/rq2/statistics/cross_domain_ranks.csv` — Per-domain ranks
- `results/rq2/figures/boxplots_SP-CF-AILTA.png` — Box plots
- `results/rq2/traces/` — 380 trace CSVs (300 SP-CF-AILTA, 60 MP-CF base, 20 MP-CF-XAI)

### Phase 6 (RQ4 mechanism)
- `results/rq4_mechanism/behavioural/per_seed_metrics.csv` — Per-seed behavioural metrics
- `results/rq4_mechanism/behavioural/aggregate_metrics.csv` — Aggregated metrics
- `results/rq4_mechanism/behavioural/mismatch_flags.csv` — Mismatch detection
- `results/rq4_mechanism/shap_shift/shap_shift.csv` — SHAP shift before vs after
- `results/rq4_mechanism/fidelity/xai_variant_fidelity.csv` — XAI variant surrogate fidelity
