package za.ac.up.cos790.hyperheuristic;

/**
 * Contract for the acceptance component of a hyper-heuristic.
 *
 * <p>An acceptance strategy decides, after a low-level heuristic has been applied,
 * whether the resulting candidate solution replaces the current incumbent. It has
 * access only to objective values and iteration metadata; it must not see any
 * domain-specific solution content.
 */
public interface AcceptanceStrategy {

    /**
     * Decides whether to accept the candidate solution as the new incumbent.
     *
     * @param incumbentObjective objective value of the current incumbent solution
     * @param candidateObjective objective value of the candidate solution produced
     *                           by the most recent heuristic application
     * @param bestSoFar          best objective value seen at any point in the run
     * @param iterationIndex     zero-based iteration counter
     * @return {@code true} if the candidate should replace the incumbent
     */
    boolean accept(double incumbentObjective,
                   double candidateObjective,
                   double bestSoFar,
                   long iterationIndex);
}
