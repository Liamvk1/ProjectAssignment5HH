package za.ac.up.cos790.acceptance;

import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;

/**
 * Acceptance strategy that always accepts the candidate solution regardless of quality.
 *
 * <p>This is the most permissive acceptance criterion and functions as a diagnostic
 * baseline. It should not be used in serious experiments.
 *
 * <p>This class is a stub. See design decision DD-02.
 */
public final class NaiveAcceptance implements AcceptanceStrategy {

    /** Constructs a naive (always-accept) acceptance strategy. */
    public NaiveAcceptance() {}

    /**
     * Always accepts the candidate solution.
     *
     * @param incumbentObjective unused
     * @param candidateObjective unused
     * @param bestSoFar          unused
     * @param iterationIndex     unused
     * @return always {@code true}
     */
    @Override
    public boolean accept(final double incumbentObjective,
                          final double candidateObjective,
                          final double bestSoFar,
                          final long iterationIndex) {
        // TODO (DD-02): Confirm whether an all-accepting strategy is useful as a baseline
        //               or whether it should be removed in favour of ImprovingOrEqual.
        return true;
    }
}
