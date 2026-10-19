# Changes from Assessment 4 to Assessment 5

## Replication (marker comment: "one run per cell, no variance estimate")

- **10 independent seeds per technique per domain** (was 1 seed). Seeds are fixed in `config/seeds.txt` and recorded in every manifest.
- **240 total runs** (4 techniques x 6 domains x 10 seeds), up from 24.
- **Wilcoxon signed-rank tests** (paired by seed) with Holm correction for within-domain comparisons.
- **Vargha-Delaney A12 effect sizes** reported alongside every p-value.
- **Friedman test** with Nemenyi/Holm post-hoc for cross-domain ranking.
- Per-domain summary tables report median, IQR, mean, SD, min, max, and run count.

## CHeSC comparability (marker comment: "objective values are not comparable to published CHeSC results")

- **Deleted** the Section 2.1 sentence claiming comparability with published CHeSC results.
- **Added limitation**: comparison with CHeSC would need its normalised 10-minute time limit, competition instances, and 31 runs, which this study does not match.
- **Added budget explanation**: same application budget for all techniques within a domain; per-domain budgets set from convergence curves.
- **Added cross-domain method**: cross-domain comparisons use ranks and normalised scores, never raw objective values.

## SHAP inconsistencies (marker comment: "cross-technique SHAP magnitudes compared despite caption warning")

- **Excluded feat_llh_count** from all surrogates. It is constant within a domain and acted as a domain label in Assessment 4.
- **Per-domain surrogates**: one surrogate per technique per domain per seed (was one pooled surrogate per technique across domains).
- **Ranks and shares** replace raw SHAP magnitudes for all cross-technique comparisons.
- **Fidelity reported** for every surrogate (5-fold CV accuracy, ROC-AUC, majority baseline). Surrogates with ROC-AUC < 0.6 are flagged and excluded from SHAP reporting.
- **Stability**: Kendall's tau between per-seed SHAP rankings, averaged per technique-domain pair.
- Specific sentences in Section 5.4 corrected (see `docs/rewrite-5.4.md`).

## Overall (marker comment: "justify every component, state analysis goals early")

- **Four research questions** (RQ1-RQ4) stated in `docs/research-questions.md` and referenced throughout the analysis.
- **Design justification table** in `docs/design-justification.md`: one row per component with rationale, alternatives, and evidence.
- **Run counts corrected** to match everywhere (Assessment 4 mixed 24 and 25 runs in different places).
