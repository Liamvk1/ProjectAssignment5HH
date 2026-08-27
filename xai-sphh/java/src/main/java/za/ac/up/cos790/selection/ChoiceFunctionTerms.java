package za.ac.up.cos790.selection;

import java.util.Arrays;

/**
 * Holds the three term values used by the Choice Function selection strategy.
 *
 * <p>The Choice Function (Cowling, Kendall, Soubeiga 2001) scores each heuristic
 * as a weighted combination of three terms:
 * <ul>
 *   <li><b>f1</b>: recent improvement of the heuristic (a vector of length n).</li>
 *   <li><b>f2</b>: improvement of heuristic j when applied immediately after
 *       heuristic i (an n x n matrix, since it depends on the specific predecessor).
 *       This must be a matrix, not a flat vector, because the f2 score of heuristic j
 *       differs depending on which heuristic i preceded it.</li>
 *   <li><b>f3</b>: time elapsed since the heuristic was last called (a vector of length n).</li>
 * </ul>
 *
 * <p>All arrays are initialised to zero. Update rules are implemented in
 * {@link ChoiceFunction} and are currently stubs.
 */
public final class ChoiceFunctionTerms {

    /** f1[i]: recent improvement reward for heuristic i. */
    private final double[] f1;

    /**
     * f2[i][j]: improvement of heuristic j when applied immediately after heuristic i.
     * Indexed as f2[predecessor][successor].
     */
    private final double[][] f2;

    /** f3[i]: time (in iterations or milliseconds) since heuristic i was last applied. */
    private final double[] f3;

    /**
     * Creates zero-initialised term arrays for the given number of heuristics.
     *
     * @param heuristicCount the number of low-level heuristics in the domain
     */
    public ChoiceFunctionTerms(final int heuristicCount) {
        this.f1 = new double[heuristicCount];
        this.f2 = new double[heuristicCount][heuristicCount];
        this.f3 = new double[heuristicCount];
    }

    /**
     * Returns the f1 term for the given heuristic.
     *
     * @param heuristicIndex heuristic index
     * @return f1 value
     */
    public double getF1(final int heuristicIndex) {
        return f1[heuristicIndex];
    }

    /**
     * Sets the f1 term for the given heuristic.
     *
     * @param heuristicIndex heuristic index
     * @param value          new f1 value
     */
    public void setF1(final int heuristicIndex, final double value) {
        f1[heuristicIndex] = value;
    }

    /**
     * Returns the f2 term for heuristic {@code successor} when preceded by {@code predecessor}.
     *
     * @param predecessor index of the heuristic applied in the previous step
     * @param successor   index of the heuristic under consideration
     * @return f2 value for this pair
     */
    public double getF2(final int predecessor, final int successor) {
        return f2[predecessor][successor];
    }

    /**
     * Sets the f2 term for heuristic {@code successor} when preceded by {@code predecessor}.
     *
     * @param predecessor index of the preceding heuristic
     * @param successor   index of the succeeding heuristic
     * @param value       new f2 value
     */
    public void setF2(final int predecessor, final int successor, final double value) {
        f2[predecessor][successor] = value;
    }

    /**
     * Returns the f3 term for the given heuristic.
     *
     * @param heuristicIndex heuristic index
     * @return f3 value (elapsed time since last call)
     */
    public double getF3(final int heuristicIndex) {
        return f3[heuristicIndex];
    }

    /**
     * Sets the f3 term for the given heuristic.
     *
     * @param heuristicIndex heuristic index
     * @param value          new f3 value
     */
    public void setF3(final int heuristicIndex, final double value) {
        f3[heuristicIndex] = value;
    }

    /**
     * Returns the number of heuristics this term set was created for.
     *
     * @return heuristic count
     */
    public int heuristicCount() {
        return f1.length;
    }
}
