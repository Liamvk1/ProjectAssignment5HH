package za.ac.up.cos790.acceptance;

import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;

/**
 * Acceptance strategy that accepts the candidate solution only when it is at least as
 * good as the incumbent (i.e. its objective value does not increase for minimisation).
 *
 * <p>This is a standard deterministic acceptance criterion with no parameters to tune.
 *
 * <p>This class is a stub. See design decision DD-02.
 */
public final class ImprovingOrEqual implements AcceptanceStrategy {

    /** Constructs an improving-or-equal acceptance strategy. */
    public ImprovingOrEqual() {}

    /**
     * Accepts the candidate if its objective is less than or equal to the incumbent's.
     *
     * @param incumbentObjective objective value of the current incumbent
     * @param candidateObjective objective value of the candidate
     * @param bestSoFar          best objective seen so far (unused by this strategy)
     * @param iterationIndex     current iteration (unused by this strategy)
     * @return {@code true} if {@code candidateObjective <= incumbentObjective}
     */
    @Override
    public boolean accept(final double incumbentObjective,
                          final double candidateObjective,
                          final double bestSoFar,
                          final long iterationIndex) {
        // TODO (DD-02): Verify the convention: is this problem minimisation or maximisation?
        //               The current implementation assumes minimisation throughout.
        return candidateObjective <= incumbentObjective;
    }
}
