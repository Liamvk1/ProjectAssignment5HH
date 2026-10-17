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
 * @param heuristicCount              Total number of low-level heuristics available.
 * @param iterationIndex              Zero-based iteration counter for the current run.
 * @param budgetProgress              Normalised progress (0.0 at start, 1.0 at budget exhaustion).
 * @param currentObjective            Objective value of the current incumbent solution.
 * @param bestSoFar                   Best objective value seen at any point in the run.
 * @param iterationsSinceImprovement  Consecutive iterations without improvement to best.
 * @param iterationsSinceAccept       Consecutive iterations since the last accepted move.
 * @param runningMin                  Minimum objective observed so far (for normalisation).
 *                                    Must use only values observed up to the current step;
 *                                    using the full-run range leaks future information.
 * @param runningMax                  Maximum objective observed so far (for normalisation).
 *                                    Same constraint: running extrema only.
 * @param recentDeltas                Window of recent objective deltas (after - before),
 *                                    newest first. Length up to {@link #WINDOW_SIZE}.
 *                                    Negative deltas represent improvement for minimisation.
 * @param recentLogReturns            Window of recent log returns, newest first. Length up to
 *                                    {@link #WINDOW_SIZE}. NaN entries indicate steps where
 *                                    the log return was undefined (non-positive objectives).
 * @param lastHeuristics              Indices of the last {@link #HISTORY_LENGTH} heuristics
 *                                    applied, newest first. Missing entries are -1.
 * @param lastHeuristicClasses        Ordinal of the HeuristicType for each of the last
 *                                    {@link #HISTORY_LENGTH} heuristics, newest first.
 *                                    Missing entries are -1. Ordinals follow the HeuristicType
 *                                    enum declaration order: MUTATION=0, RUIN_RECREATE=1,
 *                                    LOCAL_SEARCH=2, CROSSOVER=3.
 * @param populationBest              Best objective in the population. NaN for single-point.
 * @param populationMean              Mean objective across the population. NaN for single-point.
 * @param populationDiversity         Standard deviation of population objectives divided by
 *                                    their mean. NaN for single-point or when mean is zero.
 * @param populationTargetRank        Rank of the target individual (0 = best). -1 for
 *                                    single-point search.
 */
public record SearchState(
        int     heuristicCount,
        long    iterationIndex,
        double  budgetProgress,
        double  currentObjective,
        double  bestSoFar,
        long    iterationsSinceImprovement,
        long    iterationsSinceAccept,
        double  runningMin,
        double  runningMax,
        List<Double>  recentDeltas,
        List<Double>  recentLogReturns,
        List<Integer> lastHeuristics,
        List<Integer> lastHeuristicClasses,
        double  populationBest,
        double  populationMean,
        double  populationDiversity,
        int     populationTargetRank
) {

    /**
     * Window length for the recent delta and log-return lists. Set to 50 to support
     * feat_improve_rate_50 and feat_mean_logret_50 (Decision 28).
     */
    public static final int WINDOW_SIZE = 50;

    /** History length for previously applied heuristic indices and classes. */
    public static final int HISTORY_LENGTH = 3;

    /**
     * Compact constructor that defensively copies all mutable list arguments.
     */
    public SearchState {
        recentDeltas          = List.copyOf(recentDeltas);
        recentLogReturns      = List.copyOf(recentLogReturns);
        lastHeuristics        = List.copyOf(lastHeuristics);
        lastHeuristicClasses  = List.copyOf(lastHeuristicClasses);
    }

    /**
     * Creates a minimal single-point snapshot for use in tests or the first iteration.
     * Population fields are filled with their single-point sentinel values.
     */
    public static SearchState singlePoint(
            final int heuristicCount,
            final long iterationIndex,
            final double budgetProgress,
            final double currentObjective,
            final double bestSoFar,
            final long iterationsSinceImprovement,
            final long iterationsSinceAccept,
            final double runningMin,
            final double runningMax,
            final List<Double>  recentDeltas,
            final List<Double>  recentLogReturns,
            final List<Integer> lastHeuristics,
            final List<Integer> lastHeuristicClasses) {
        return new SearchState(
                heuristicCount, iterationIndex, budgetProgress,
                currentObjective, bestSoFar,
                iterationsSinceImprovement, iterationsSinceAccept,
                runningMin, runningMax,
                recentDeltas, recentLogReturns,
                lastHeuristics, lastHeuristicClasses,
                Double.NaN, Double.NaN, Double.NaN, -1);
    }
}
