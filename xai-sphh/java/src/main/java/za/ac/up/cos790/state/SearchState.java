package za.ac.up.cos790.state;

import java.util.List;

/**
 * Immutable snapshot of everything the hyper-heuristic is legally allowed to observe
 * at a single decision point.
 *
 * <p><strong>Domain barrier:</strong> this record must contain no problem-specific
 * information. All fields are derived solely from objective values, iteration counts,
 * heuristic indices and heuristic classes. Adding any field that encodes domain
 * structure (variable assignments, graph topology, schedule slots, etc.) violates
 * the defining property of a hyper-heuristic and must not be done.
 *
 * @param heuristicCount            Total number of low-level heuristics available.
 * @param iterationIndex            Zero-based iteration counter for the current run.
 * @param budgetProgress            Normalised progress (0.0 at start, 1.0 at budget exhaustion).
 * @param currentObjective          Objective value of the current incumbent solution.
 * @param bestSoFar                 Best objective value seen at any point in the run.
 * @param iterationsSinceImprovement Number of consecutive iterations without improvement to best.
 * @param recentDeltas              Fixed-length window of recent objective deltas, newest first.
 *                                  Positions beyond the run history are filled with 0.0.
 * @param lastHeuristics            Identities (indices) of the last k heuristics applied,
 *                                  newest first. Positions beyond the run history are filled
 *                                  with -1 to indicate no heuristic.
 */
public record SearchState(
        int heuristicCount,
        long iterationIndex,
        double budgetProgress,
        double currentObjective,
        double bestSoFar,
        long iterationsSinceImprovement,
        List<Double> recentDeltas,
        List<Integer> lastHeuristics
) {

    /** Window length for recent objective deltas. */
    public static final int DELTA_WINDOW = 5;

    /** History length for previously applied heuristic indices. */
    public static final int HISTORY_LENGTH = 3;

    /**
     * Compact constructor that defensively copies mutable list arguments.
     */
    public SearchState {
        recentDeltas  = List.copyOf(recentDeltas);
        lastHeuristics = List.copyOf(lastHeuristics);
    }
}
