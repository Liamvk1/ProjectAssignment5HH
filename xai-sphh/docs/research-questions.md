# Research Questions

## RQ1: Within-domain technique performance

**Does any technique outperform the Simple Random baseline with statistical support within each domain?**

Evidence: Task 3 within-domain tables. For each domain, the Wilcoxon signed-rank test (paired by seed) compares each technique against SP-SR-LA. Holm correction is applied within each domain. Vargha-Delaney A12 effect sizes accompany every comparison.

Outputs:
- `results/a5/statistics/per_domain_summary.csv` (median, IQR, mean, SD, min, max per technique per domain)
- `results/a5/statistics/wilcoxon_tests.csv` (corrected p-values and A12 per comparison)
- `results/a5/figures/boxplots_per_domain.png`


## RQ2: Cross-domain technique ranking

**Which technique performs best across domains?**

Evidence: Task 3 cross-domain analysis. Techniques are ranked within each domain by median (1 = best, average ties). Medians are normalised to [0, 1] per domain. Mean rank and mean normalised score are reported per technique. The Friedman test treats domains as blocks and techniques as treatments, followed by Nemenyi or Holm-corrected pairwise tests if significant.

Outputs:
- `results/a5/statistics/cross_domain_ranks.csv`
- `results/a5/statistics/friedman_test.txt`


## RQ3: Feature importance and stability

**Which state features drive acceptance within each technique, and are these explanations stable across seeds?**

Evidence: Task 4 SHAP analysis. Per-domain, per-technique surrogates are trained (one per seed, 10 total). Mean |SHAP| shares and ranks are computed per feature. Stability is measured by Kendall's tau between per-seed rankings, averaged per technique-domain pair. Only surrogates with ROC-AUC >= 0.6 are reported.

Outputs:
- `results/a5/shap/shares_and_ranks_per_domain.csv`
- `results/a5/shap/heatmaps_per_domain.png`
- `results/a5/shap/stability_kendall_tau.csv`
- `results/a5/shap/fidelity_report.csv`


## RQ4: Feature differences across strategies

**Do the features that drive acceptance differ between selection strategies, acceptance strategies, and search topologies?**

Evidence: Task 4 rank comparisons across techniques within each domain. Comparisons use ranks or shares, never raw SHAP magnitudes.

Outputs:
- `results/a5/shap/shares_and_ranks_per_domain.csv` (compare columns across techniques)
- `results/a5/shap/heatmaps_per_domain.png` (visual comparison)
