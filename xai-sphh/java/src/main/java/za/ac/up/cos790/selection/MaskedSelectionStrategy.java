package za.ac.up.cos790.selection;

import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
import za.ac.up.cos790.instrumentation.ScoreVector;
import za.ac.up.cos790.state.SearchState;

import java.util.Random;
import java.util.Set;

/**
 * Decorator that restricts an underlying {@link SelectionStrategy} to only select
 * from heuristics allowed by a {@link SelectionMask}.
 *
 * <p>The mask is phase-dependent: allowed heuristics change based on budget progress.
 * The underlying strategy (e.g. ChoiceFunction) still computes scores for all
 * heuristics, but this decorator overrides the selection to pick the best-scoring
 * heuristic among the allowed set.
 *
 * <p>CF scores, phi updates and f1/f2/f3 bookkeeping continue unchanged for all
 * heuristics — the mask only affects which heuristic is actually selected.
 * This ensures the CF maintains accurate historical information even for
 * temporarily excluded heuristics that may become allowed in a later phase.
 *
 * <p>During the CF warm-up period, the mask is applied to skip excluded heuristics
 * in the warm-up sequence. This means excluded heuristics will not be warmed up
 * in their excluded phases but will still be warmed up if they become allowed later.
 */
public final class MaskedSelectionStrategy implements SelectionStrategy {

    private final SelectionStrategy delegate;
    private final SelectionMask mask;
    private final Random tieBreaker;

    /** Tracks whether the mask was active at the last selection. */
    private boolean lastMaskActive = false;

    /** Number of allowed heuristics at the last selection. */
    private int lastAllowedCount = 0;

    /**
     * Constructs a masked selection strategy.
     *
     * @param delegate the underlying selection strategy
     * @param mask     the phase-dependent selection mask
     * @param seed     random seed for tie-breaking among masked heuristics
     */
    public MaskedSelectionStrategy(final SelectionStrategy delegate,
                                    final SelectionMask mask,
                                    final long seed) {
        this.delegate   = delegate;
        this.mask       = mask;
        this.tieBreaker = new Random(seed + 777L); // distinct stream
    }

    /**
     * Selects a heuristic by first asking the delegate for scores, then picking
     * the highest-scoring heuristic among those allowed by the mask.
     *
     * <p>The delegate's {@code select()} is called to trigger its internal state
     * updates (e.g. CF warm-up counter advance), but its return value is overridden
     * with the mask-constrained argmax of the score vector.
     */
    @Override
    public int select(final SearchState state) {
        // Let the delegate compute its selection and update internal state.
        final int delegateChoice = delegate.select(state);
        final ScoreVector scores = delegate.scoreVector();
        final int n = state.heuristicCount();

        final Set<Integer> allowed = mask.allowedHeuristics(state.budgetProgress());
        lastAllowedCount = allowed.size();

        // If all heuristics are allowed, use the delegate's choice directly.
        if (allowed.size() >= n) {
            lastMaskActive = false;
            return delegateChoice;
        }
        lastMaskActive = true;

        // If the delegate's choice is allowed, use it (covers warm-up).
        if (allowed.contains(delegateChoice)) {
            return delegateChoice;
        }

        // During warm-up (all scores NaN), pick the first allowed heuristic
        // that hasn't been warmed up yet (or any allowed one).
        if (scores.size() > 0 && Double.isNaN(scores.get(0))) {
            // Find any allowed heuristic
            for (final int h : allowed) {
                return h;
            }
        }

        // Normal operation: argmax over allowed heuristics only.
        return maskedArgmax(scores, allowed, n);
    }

    /**
     * Forwards outcome to the delegate unchanged.
     * CF scores continue to be updated for all heuristics.
     */
    @Override
    public void recordOutcome(final int heuristicIndex,
                               final double objectiveDelta,
                               final double cpuTimeMs) {
        delegate.recordOutcome(heuristicIndex, objectiveDelta, cpuTimeMs);
    }

    /**
     * Returns the delegate's score vector unchanged.
     */
    @Override
    public ScoreVector scoreVector() {
        return delegate.scoreVector();
    }

    /**
     * Returns whether the mask was active at the last selection point.
     * Used by the trace writer to log mask status.
     */
    public boolean wasMaskActive() {
        return lastMaskActive;
    }

    /**
     * Returns the number of allowed heuristics at the last selection point.
     */
    public int lastAllowedSetSize() {
        return lastAllowedCount;
    }

    /**
     * Returns the underlying selection mask.
     */
    public SelectionMask getMask() {
        return mask;
    }

    /**
     * Returns the argmax of scores restricted to the allowed set.
     * Ties are broken by uniform random draw from the tie-breaker stream.
     */
    private int maskedArgmax(final ScoreVector scores, final Set<Integer> allowed, final int n) {
        double best = Double.NEGATIVE_INFINITY;
        for (final int h : allowed) {
            if (h < scores.size()) {
                final double s = scores.get(h);
                if (!Double.isNaN(s) && s > best) {
                    best = s;
                }
            }
        }

        // Count ties among allowed heuristics.
        int tieCount = 0;
        for (final int h : allowed) {
            if (h < scores.size() && scores.get(h) == best) {
                tieCount++;
            }
        }

        if (tieCount <= 1) {
            for (final int h : allowed) {
                if (h < scores.size() && scores.get(h) == best) {
                    return h;
                }
            }
        }

        // Multiple ties: draw uniformly.
        int target = tieBreaker.nextInt(tieCount);
        for (final int h : allowed) {
            if (h < scores.size() && scores.get(h) == best) {
                if (target == 0) return h;
                target--;
            }
        }

        // Fallback (unreachable): return the first allowed heuristic.
        return allowed.iterator().next();
    }
}
