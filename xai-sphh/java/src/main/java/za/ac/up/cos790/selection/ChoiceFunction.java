package za.ac.up.cos790.selection;

import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
import za.ac.up.cos790.instrumentation.ScoreVector;
import za.ac.up.cos790.state.SearchState;

import java.util.Random;

/**
 * Modified Choice Function selection strategy (Cowling, Kendall and Soubeiga 2001;
 * adaptive weighting after Tyasnurita, Ozcan and John 2017).
 *
 * <p>Scores each heuristic h as:
 * <pre>CF(h) = phi * f1[h] + phi * f2[lastH][h] + (1 - phi) * f3[h]</pre>
 * where:
 * <ul>
 *   <li>f1[h]: accumulated improvement of h applied alone, with exponential decay.</li>
 *   <li>f2[i][j]: accumulated improvement of j applied immediately after i; zero when
 *       no predecessor exists. The matrix is asymmetric: f2[i][j] != f2[j][i].</li>
 *   <li>f3[h]: elapsed CPU time since h was last applied.</li>
 *   <li>phi: adaptive weight that shifts the balance between historical performance
 *       (f1, f2) and idle time (f3).</li>
 * </ul>
 *
 * <p>Update rules (design decision Q09, Modified Choice Function):
 * <ul>
 *   <li>phi snaps to 0.99 on an improving move (objective fell for minimisation).</li>
 *   <li>phi decays by 0.01 per non-improving step, floored at 0.01.</li>
 *   <li>f3 weight = 1 - phi, so a stalling search shifts weight towards idle time.</li>
 *   <li>f1 and f2 are updated as: new = reward + phi * old.</li>
 *   <li>reward = (objectiveBefore - objectiveAfter) / max(cpuTimeMs, MIN_TIME_MS).</li>
 * </ul>
 *
 * <p>Assumption: phi starts at 0.99 (the reward value). Neither Modified Choice
 * Function paper states the initial value; starting at 0.99 means the search begins
 * by intensifying on historical performance rather than idle time.
 *
 * <p>Selection rule: argmax, with ties broken by a uniform random draw from a stream
 * seeded at construction. The tie-breaking stream is independent of other random
 * components so that adding new components later does not shift earlier decisions (Q11).
 *
 * <p>Initialisation: a warm-up pass applies each pooled heuristic exactly once in
 * ascending index order before scoring begins. This gives f1 at least one observation
 * per heuristic and avoids an arbitrary score for unobserved heuristics. Warm-up
 * iterations are drawn from the ordinary budget. The score vector is all NaN during
 * warm-up, making warm-up rows identifiable in the trace (Q12).
 */
public final class ChoiceFunction implements SelectionStrategy {

    /** Phi value restored on an improving move (Modified Choice Function constant). */
    private static final double PHI_REWARD = 0.99;

    /** Floor below which phi cannot fall. */
    private static final double PHI_FLOOR = 0.01;

    /** Per-step decay applied to phi on a non-improving move. */
    private static final double PHI_DECAY = 0.01;

    /**
     * Minimum CPU time used as divisor when computing reward per unit time.
     * Prevents division by zero on coarse-grained system clocks.
     */
    private static final double MIN_TIME_MS = 1.0;

    /**
     * Adaptive weight. Assumption: starts at PHI_REWARD so that the search
     * begins by intensifying rather than diversifying.
     */
    private double phi = PHI_REWARD;

    /** Seeded stream used exclusively for tie-breaking in argmax. */
    private final Random tieBreaker;

    /** Term values for f1, f2, f3. Initialised on first call to {@link #select}. */
    private ChoiceFunctionTerms terms;

    /** Score vector produced at the most recent decision point. */
    private ScoreVector lastScores;

    /**
     * Index of the heuristic applied at the previous step.
     * -1 before the first application, so the f2 pair term contributes zero.
     */
    private int lastSelected = -1;

    /**
     * Warm-up counter. For the first {@code heuristicCount} calls to {@link #select},
     * heuristics are returned in ascending order and scores are all NaN.
     */
    private int warmupIndex = 0;

    /**
     * Constructs a Choice Function selector.
     *
     * @param seed random seed for the tie-breaking stream; derived separately from
     *             other random streams so that adding new components does not shift
     *             this stream and break reproducibility (Q11)
     */
    public ChoiceFunction(final long seed) {
        this.tieBreaker = new Random(seed);
    }

    /**
     * Selects the heuristic with the highest Choice Function score.
     *
     * <p>During the warm-up pass the heuristics are returned in ascending index
     * order and the score vector is all NaN. After warm-up, scores are computed
     * from f1, f2 and f3 and the highest-scoring heuristic is returned.
     *
     * @param state current search state snapshot
     * @return zero-based index of the selected heuristic
     */
    @Override
    public int select(final SearchState state) {
        if (terms == null || terms.heuristicCount() != state.heuristicCount()) {
            terms      = new ChoiceFunctionTerms(state.heuristicCount());
            warmupIndex = 0;
            lastScores  = ScoreVector.nanVector(state.heuristicCount());
        }

        final int n = state.heuristicCount();

        // Warm-up: return heuristics 0..n-1 in order before scoring begins.
        // Score vector is NaN so that warm-up rows are identifiable in the trace.
        if (warmupIndex < n) {
            lastScores = ScoreVector.nanVector(n);
            return warmupIndex++;
        }

        // Normal scoring: compute composite score for every heuristic.
        final double[] rawScores = new double[n];
        for (int h = 0; h < n; h++) {
            // f2 contributes zero when no predecessor has been observed.
            final double f2 = (lastSelected >= 0)
                    ? terms.getF2(lastSelected, h)
                    : 0.0;
            rawScores[h] = phi * terms.getF1(h)
                         + phi * f2
                         + (1.0 - phi) * terms.getF3(h);
        }
        lastScores = new ScoreVector(rawScores);

        return argmax(rawScores);
    }

    /**
     * Updates f1, f2 and f3 and adjusts the adaptive weight based on the outcome.
     *
     * <p>The reward is improvement per unit of CPU time. For minimisation, a negative
     * objective delta means improvement, so the reward is {@code -objectiveDelta / elapsed}.
     * Sign handling is intentional: delta = after - before, so a decrease gives a
     * positive reward.
     *
     * @param heuristicIndex index of the heuristic that was applied
     * @param objectiveDelta {@code objectiveAfter - objectiveBefore}; negative
     *                       values indicate improvement for minimisation problems
     * @param cpuTimeMs      wall-clock time consumed by the application
     */
    @Override
    public void recordOutcome(final int heuristicIndex,
                               final double objectiveDelta,
                               final double cpuTimeMs) {
        if (terms == null) {
            return;
        }

        final double elapsed = Math.max(cpuTimeMs, MIN_TIME_MS);
        final double reward  = -objectiveDelta / elapsed;

        // Update f1 for the applied heuristic using exponential decay with phi.
        terms.setF1(heuristicIndex,
                reward + phi * terms.getF1(heuristicIndex));

        // Update f2 for the (lastSelected, heuristicIndex) pair.
        // This is asymmetric: applying j after i updates f2[i][j], not f2[j][i] (Q08).
        if (lastSelected >= 0) {
            terms.setF2(lastSelected, heuristicIndex,
                    reward + phi * terms.getF2(lastSelected, heuristicIndex));
        }

        // f3: reset for the applied heuristic; increment for all others.
        // This measures elapsed time since each heuristic was last called.
        for (int k = 0; k < terms.heuristicCount(); k++) {
            if (k == heuristicIndex) {
                terms.setF3(k, 0.0);
            } else {
                terms.setF3(k, terms.getF3(k) + elapsed);
            }
        }

        // Adjust phi: snap back to PHI_REWARD on an improving move (delta < 0
        // for minimisation); otherwise decay by PHI_DECAY, floored at PHI_FLOOR.
        if (objectiveDelta < 0.0) {
            phi = PHI_REWARD;
        } else {
            phi = Math.max(PHI_FLOOR, phi - PHI_DECAY);
        }

        lastSelected = heuristicIndex;
    }

    /**
     * Returns the score vector computed at the most recent decision point.
     * All entries are NaN during the warm-up pass.
     *
     * @return per-heuristic score vector
     */
    @Override
    public ScoreVector scoreVector() {
        return lastScores != null ? lastScores : ScoreVector.nanVector(0);
    }

    /**
     * Returns the index of the highest-scoring heuristic. Ties are broken by a
     * uniform random draw from the seeded tie-breaking stream (Q11).
     */
    private int argmax(final double[] scores) {
        double best = Double.NEGATIVE_INFINITY;
        for (final double s : scores) {
            if (s > best) {
                best = s;
            }
        }

        // Count tied heuristics.
        int tieCount = 0;
        for (final double s : scores) {
            if (s == best) {
                tieCount++;
            }
        }

        // Single winner: find it without consuming the RNG.
        if (tieCount == 1) {
            for (int h = 0; h < scores.length; h++) {
                if (scores[h] == best) {
                    return h;
                }
            }
        }

        // Multiple ties: draw uniformly among all tied heuristics.
        int target = tieBreaker.nextInt(tieCount);
        for (int h = 0; h < scores.length; h++) {
            if (scores[h] == best) {
                if (target == 0) {
                    return h;
                }
                target--;
            }
        }

        // Unreachable: the loop above always returns within bounds.
        return 0;
    }
}
