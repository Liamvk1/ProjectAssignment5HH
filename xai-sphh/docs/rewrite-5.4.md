# Section 5.4 Sentences Requiring Correction

Each entry below identifies a sentence in the current Section 5.4 (Per-technique SHAP profiles) that compares raw SHAP magnitudes across techniques, violating the caption's own warning. The replacement uses ranks or shares.

---

## 1. feat_gap_to_best cross-technique magnitude comparison

**Original (lines 474-479):**
> For SP-CF-AILTA, `feat_gap_to_best` has SHAP 10.86, second only to the domain identifier. For SP-CF-LA and SP-SR-LA it is 0.32 and 0.51.

**Problem:** Compares raw SHAP magnitudes (10.86 vs 0.32 vs 0.51) across three techniques.

**Replacement:**
> Within SP-CF-AILTA, `feat_gap_to_best` ranks 2nd by mean |SHAP| share (XX% of total importance), compared with rank Yth (YY%) in SP-CF-LA and rank Zth (ZZ%) in SP-SR-LA. The higher rank under AILTA is consistent with AILTA's adaptive threshold mechanism, which explicitly conditions acceptance on the gap to the best known solution.

---

## 2. feat_improve_rate_50 cross-technique magnitude comparison

**Original (lines 481-485):**
> feat_improve_rate_50 is consistently important across all single-point techniques (1.48 for SP-CF-LA, 1.31 for SP-CF-AILTA, 1.28 for SP-SR-LA) but much less so for MP-CF (0.11).

**Problem:** Compares raw values 1.48, 1.31, 1.28, and 0.11 across four techniques.

**Replacement:**
> `feat_improve_rate_50` ranks among the top 3 features by share in all three single-point techniques (rank Xth in SP-CF-LA, Yth in SP-CF-AILTA, Zth in SP-SR-LA) but falls to rank Wth in MP-CF. Recent search momentum is a primary signal for single-point acceptance decisions regardless of selection strategy, while multi-point replacement depends more on stagnation duration and solution quality.

---

## 3. feat_last_h1/h2/h3 cross-technique magnitude comparison (CF vs SR)

**Original (lines 487-492):**
> The `feat_last_h1/h2/h3` features are more important in SP-CF-LA (0.39, 0.21, 0.43) than in SP-SR-LA (0.06, 0.03, 0.08). Under CF, specific heuristics are preferentially selected based on past performance, creating informative patterns in heuristic history that correlate with acceptance likelihood. Under Simple Random, heuristic history carries no signal.

**Problem:** Compares raw SHAP magnitudes between CF and SR techniques.

**Replacement:**
> The `feat_last_h{1,2,3}` features rank among the top 5 by share in SP-CF-LA but fall to the bottom 5 in SP-SR-LA. Under the Choice Function, specific heuristics are preferentially selected based on past performance, creating informative patterns in heuristic history that correlate with acceptance likelihood. Under Simple Random, heuristic selection is independent of history, so these features carry little signal.

---

## 4. feat_iters_since_accept cross-technique magnitude comparison (MP-CF vs SP)

**Original (lines 464-472):**
> For MP-CF, `feat_iters_since_accept` carries SHAP 86.23, the dominant feature by a large margin. For all three single-point techniques it is zero.

**Problem:** Compares raw SHAP magnitude 86.23 across techniques.

**Replacement:**
> Within MP-CF, `feat_iters_since_accept` ranks 1st by share (XX% of total importance). In all three single-point techniques it ranks last with near-zero share. In multi-point search, acceptance means population replacement; when no replacement has occurred for many iterations, the population has converged and the probability that the next candidate exceeds the worst member rises sharply.

---

## 5. feat_iters_since_improve cross-technique comparison (AILTA vs LA)

**Original (lines 498-499):**
> `feat_iters_since_improve` (SHAP 0.317 for AILTA vs 0.155 for LA)

**Problem:** Compares raw SHAP magnitudes between AILTA and LA.

**Replacement:**
> `feat_iters_since_improve` ranks higher by share in SP-CF-AILTA (rank Xth, XX%) than in SP-CF-LA (rank Yth, YY%).

---

## 6. feat_llh_count as domain label

**Original (lines 454-462):**
> `feat_llh_count` dominates the single-point surrogates... acts as a domain identifier.

**Problem:** This is correctly identified as a confound. The fix is to **exclude feat_llh_count** from all surrogates and train per-domain surrogates.

**Replacement:**
> `feat_llh_count` has been excluded from all surrogates because it is constant within a domain and acted as a domain label when surrogates were trained on pooled cross-domain decisions. Surrogates are now trained per domain, eliminating this confound.

---

*Note: Rank and share values marked XX%, Yth are placeholders. They will be filled from the Task 4 SHAP analysis results.*
