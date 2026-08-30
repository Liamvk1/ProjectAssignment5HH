package za.ac.up.cos790.acceptance;

import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;

/**
 * Adaptive Iteration Limited Threshold Accepting (AILTA) acceptance strategy.
 *
 * <p>Maintains a threshold that decays linearly from an initial value (2% of the
 * absolute starting objective) down to zero over the run. The candidate solution
 * is accepted when the worsening, i.e. {@code candidateObjective - incumbentObjective}
 * for minimisation, does not exceed the current threshold.
 *
 * <p>This strategy is included because the project assessment names it explicitly
 * alongside accept-all, improving-or-equal, and Late Acceptance as the four required
 * move acceptance criteria (design decision DD-02, Member 4). Simulated Annealing is
 * retained separately as an ablation comparison for Member 2.
 *
 * <p>Threshold formula: {@code threshold(t) = initialThreshold * (1 - t / totalBudget)},
 * where t is the current iteration index. This is linear and reaches zero at budget
 * exhaustion, so the late-run behaviour converges to improving-or-equal.
 */
public final class AILTA implements AcceptanceStrategy {

    /** Fraction of the starting objective used as the initial threshold. */
    private static final double INITIAL_FRACTION = 0.02;

    private final double initialThreshold;
    private final long totalIterations;

    /**
     * Constructs an AILTA strategy.
     *
     * @param startingObjective objective value at the beginning of the run; the
     *                          initial threshold is {@value #INITIAL_FRACTION} of
     *                          its absolute value
     * @param totalIterations   total number of heuristic applications in the run,
     *                          used to compute the linear decay
     */
    public AILTA(final double startingObjective, final long totalIterations) {
        this.initialThreshold = INITIAL_FRACTION * Math.abs(startingObjective);
        this.totalIterations  = totalIterations;
    }

    /**
     * Accepts the candidate if the worsening does not exceed the current threshold.
     *
     * <p>The {@code bestSoFar} argument is unused by this strategy.
     *
     * @param incumbentObjective current incumbent objective
     * @param candidateObjective candidate objective
     * @param bestSoFar          best objective seen (unused)
     * @param iterationIndex     zero-based iteration counter, used for decay
     * @return {@code true} if the candidate should be accepted
     */
    @Override
    public boolean accept(final double incumbentObjective,
                          final double candidateObjective,
                          final double bestSoFar,
                          final long iterationIndex) {
        final double progress  = (totalIterations > 0)
                ? Math.min(1.0, (double) iterationIndex / totalIterations)
                : 1.0;
        final double threshold = initialThreshold * (1.0 - progress);
        final double worsening = candidateObjective - incumbentObjective;
        return worsening <= threshold;
    }
}
