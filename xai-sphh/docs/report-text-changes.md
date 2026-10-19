# Report Text Changes for Assessment 5

## 1. Delete CHeSC comparability claim (Section 2.1, line 59)

**Delete:**
> Objective values are now directly comparable to published CHeSC results.

**Keep** the preceding sentence about real HyFlex jars being present and manifests reporting `stub: false`.

---

## 2. Add CHeSC limitation (Section 7 / Limitations)

**Add:**
> Comparison with published CHeSC results would require matching its normalised 10-minute time limit, competition instances, and 31 independent runs per technique per domain. This study uses a per-domain iteration budget (set from convergence curves), instance 0 only, and 10 seeds. The results are therefore not directly comparable to CHeSC rankings, although the same real HyFlex domains are used.

---

## 3. Add budget rule explanation (Section 3 / Experimental Setup)

**Add:**
> All techniques within a domain receive the same application budget, defined as a count of heuristic applications. Per-domain budgets are set from convergence curves on a pilot run: for each domain, the budget is the smallest tier in {5,000; 10,000; 20,000; 50,000; 100,000} that exceeds the iteration at which all four techniques reach 95% of their total improvement. The resulting budgets are: SAT 50,000; BinPacking 100,000; FlowShop 100,000; TSP 10,000; VRP 50,000; PersonnelScheduling 5,000.

---

## 4. Add cross-domain comparison method (Section 5 / Analysis)

**Add:**
> Cross-domain comparisons use ranks and normalised scores, never raw objective values. Within each domain, techniques are ranked by median objective (1 = best, average ties). Medians are normalised to [0, 1] per domain: (value - best) / (worst - best). Mean rank and mean normalised score are reported per technique across all six domains.

---

## 5. Correct run counts

**Check and correct** all mentions of run counts. Assessment 4 inconsistently mentions 24 and 25 runs. The correct counts are:

- Assessment 4: 24 runs (4 techniques x 6 domains x 1 seed)
- Assessment 5: 240 runs (4 techniques x 6 domains x 10 seeds)

Search for "24 runs", "25 runs", "24 cells", "25 cells" and ensure consistency.
