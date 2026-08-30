package za.ac.up.cos790.acceptance;

import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;

/**
 * Late Acceptance Hill Climbing acceptance strategy (Burke and Bykov 2012).
 *
 * <p>Accepts the candidate if its objective is no worse than the objective recorded
 * L iterations ago, where L is the list length parameter. This allows limited
 * uphill moves without requiring a temperature schedule.
 *
 * <p>This class is a stub. See design decision DD-02 for the parameter choice.
 */
public final class LateAcceptance implements AcceptanceStrategy {

    private final int listLength;
    private double[] history;
    private int head = 0;

    /**
     * Constructs a Late Acceptance strategy with the given list length.
     *
     * @param listLength number of past objective values to retain
     */
    public LateAcceptance(final int listLength) {
        this.listLength = listLength;
        this.history = new double[listLength];
        java.util.Arrays.fill(this.history, Double.MAX_VALUE);
    }

    /**
     * Accepts the candidate if it is at least as good as the objective value from
     * {@code listLength} iterations ago.
     *
     * @param incumbentObjective current incumbent objective
     * @param candidateObjective candidate objective
     * @param bestSoFar          best objective seen (unused by this strategy)
     * @param iterationIndex     current iteration index (unused directly; history drives timing)
     * @return {@code true} if the candidate should be accepted
     */
    @Override
    public boolean accept(final double incumbentObjective,
                          final double candidateObjective,
                          final double bestSoFar,
                          final long iterationIndex) {
        // TODO (DD-02): Implement Late Acceptance. The structure is:
        //               1. Compare candidateObjective to history[head].
        //               2. If accepted, update incumbent.
        //               3. Store the new incumbent objective at history[head].
        //               4. Advance head = (head + 1) % listLength.
        throw new UnsupportedOperationException(
                "TODO (DD-02): LateAcceptance.accept is not yet implemented. "
                + "Resolve design-decisions.md DD-02 (list length parameter) first.");
    }
}
