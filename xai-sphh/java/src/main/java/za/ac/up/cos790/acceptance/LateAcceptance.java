package za.ac.up.cos790.acceptance;

import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;

import java.util.Arrays;

/**
 * Late Acceptance Hill Climbing acceptance strategy (Burke and Bykov 2012).
 *
 * <p>Accepts the candidate solution if either:
 * <ul>
 *   <li>the candidate is no worse than the current incumbent, or</li>
 *   <li>the candidate is no worse than the objective held at this position in
 *       the circular history buffer, i.e. the objective L iterations ago.</li>
 * </ul>
 *
 * <p>The history buffer is updated with the current incumbent objective only when
 * the new value is strictly better than the stored one. This prevents a worsening
 * accepted move from raising the historical baseline and making future comparisons
 * too permissive (design decision Q19).
 *
 * <p>The {@code bestSoFar} argument is intentionally unused. Comparing against the
 * best-so-far objective would turn this criterion into a strict hill climb on the
 * best value, which removes the escape mechanism the method exists to provide (Q19).
 *
 * <p>Design decision: list length L = 50, configurable via the no-arg constructor
 * or by passing an explicit value (Q18). L is a starting point, not a tuned
 * optimum; sweep over {1, 5, 50, 100, 500, 1000} before reporting a final value.
 */
public final class LateAcceptance implements AcceptanceStrategy {

    /** Default list length used when none is supplied. */
    public static final int DEFAULT_LIST_LENGTH = 50;

    private final double[] history;
    private int head = 0;

    /**
     * Constructs a Late Acceptance strategy with the given list length.
     *
     * @param listLength number of past objective values to retain (L)
     */
    public LateAcceptance(final int listLength) {
        this.history = new double[listLength];
        Arrays.fill(this.history, Double.MAX_VALUE);
    }

    /**
     * Constructs a Late Acceptance strategy with the default list length of 50.
     */
    public LateAcceptance() {
        this(DEFAULT_LIST_LENGTH);
    }

    /**
     * Accepts the candidate if it is no worse than the incumbent or no worse than
     * the objective recorded L iterations ago.
     *
     * <p>The {@code bestSoFar} argument is deliberately unused; a test asserts
     * that changing it cannot change the decision.
     *
     * @param incumbentObjective current incumbent objective (for minimisation, lower is better)
     * @param candidateObjective candidate objective produced by the heuristic application
     * @param bestSoFar          best objective seen during the run (unused by this strategy)
     * @param iterationIndex     zero-based iteration counter (unused; history drives timing)
     * @return {@code true} if the candidate should replace the incumbent
     */
    @Override
    public boolean accept(final double incumbentObjective,
                          final double candidateObjective,
                          final double bestSoFar,
                          final long iterationIndex) {

        final boolean accepted = candidateObjective <= incumbentObjective
                || candidateObjective <= history[head];

        // Update history only when the resulting incumbent is strictly better than
        // the stored value. This stops a worsening accepted move from poisoning
        // the list and making future comparisons too permissive (Q19).
        final double newIncumbent = accepted ? candidateObjective : incumbentObjective;
        if (newIncumbent < history[head]) {
            history[head] = newIncumbent;
        }

        head = (head + 1) % history.length;
        return accepted;
    }

    /**
     * Returns the fraction of history slots that have been updated from their
     * initial value. Useful for diagnostic sweeps over the list length L.
     *
     * @return a value in [0.0, 1.0]
     */
    public double acceptanceRate() {
        int populated = 0;
        for (final double v : history) {
            if (v < Double.MAX_VALUE) {
                populated++;
            }
        }
        return (double) populated / history.length;
    }
}
