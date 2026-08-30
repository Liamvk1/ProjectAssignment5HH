package za.ac.up.cos790.hyperheuristic;

import za.ac.up.cos790.instrumentation.ScoreVector;
import za.ac.up.cos790.state.SearchState;

/**
 * Contract for the selection component of a hyper-heuristic.
 *
 * <p>A selection strategy is responsible for choosing which low-level heuristic to
 * apply at each iteration and for updating its internal state based on the observed
 * outcome. It must not access any domain-specific information; it may only act on
 * the information available through {@link SearchState} and the objective values
 * reported back via {@link #recordOutcome}.
 *
 * <p>The strategy must also expose its current score vector via {@link #scoreVector}
 * so that the instrumentation layer can log the scores of all heuristics, not just
 * the one that was selected. This is necessary for explaining selection decisions.
 */
public interface SelectionStrategy {

    /**
     * Selects the index of the low-level heuristic to apply next.
     *
     * @param state the current search state snapshot
     * @return zero-based index of the chosen heuristic
     */
    int select(SearchState state);

    /**
     * Receives feedback about the outcome of applying the most recently selected heuristic.
     *
     * <p>Implementations use this to update internal scores or counters.
     *
     * @param heuristicIndex index of the heuristic that was applied
     * @param objectiveDelta change in objective value ({@code after - before})
     * @param cpuTimeMs      wall-clock time consumed by the heuristic application, in milliseconds
     */
    void recordOutcome(int heuristicIndex, double objectiveDelta, double cpuTimeMs);

    /**
     * Returns the score vector assigned to all heuristics at the current decision point.
     *
     * <p>This method is called by the instrumentation layer immediately after
     * {@link #select} to capture the scores that informed the decision. Strategies that
     * do not maintain per-heuristic scores (such as {@code SimpleRandom}) should return
     * a vector of NaN values of the correct length.
     *
     * @return the current per-heuristic score vector
     */
    ScoreVector scoreVector();
}
