package za.ac.up.cos790.instrumentation;

import java.util.Arrays;

/**
 * Snapshot of the per-heuristic selection scores held by a {@code SelectionStrategy}
 * at a single decision point.
 *
 * <p>The length of the score array matches the number of low-level heuristics available
 * in the current domain. The position of each score corresponds to the heuristic index.
 * Strategies that do not maintain per-heuristic scores populate all entries with
 * {@link Double#NaN}.
 *
 * <p>Instances are written to the trace file as columns prefixed with {@code score_}.
 */
public final class ScoreVector {

    private final double[] scores;

    /**
     * Creates a score vector by copying the supplied array.
     *
     * @param scores raw score values, one per heuristic; the array is defensively copied
     */
    public ScoreVector(final double[] scores) {
        this.scores = Arrays.copyOf(scores, scores.length);
    }

    /**
     * Returns a score vector in which every entry is {@link Double#NaN},
     * for use by strategies that do not maintain per-heuristic scores.
     *
     * @param heuristicCount number of heuristics in the domain
     * @return a NaN-filled score vector of the given length
     */
    public static ScoreVector nanVector(final int heuristicCount) {
        final double[] nans = new double[heuristicCount];
        Arrays.fill(nans, Double.NaN);
        return new ScoreVector(nans);
    }

    /**
     * Returns the score assigned to the heuristic at the given index.
     *
     * @param heuristicIndex zero-based heuristic index
     * @return the score, or {@link Double#NaN} if this strategy does not score heuristics
     */
    public double get(final int heuristicIndex) {
        return scores[heuristicIndex];
    }

    /**
     * Returns the number of heuristics represented in this vector.
     *
     * @return the length of the underlying score array
     */
    public int size() {
        return scores.length;
    }

    /**
     * Returns a defensive copy of the underlying score array.
     *
     * @return copy of all scores
     */
    public double[] toArray() {
        return Arrays.copyOf(scores, scores.length);
    }
}
