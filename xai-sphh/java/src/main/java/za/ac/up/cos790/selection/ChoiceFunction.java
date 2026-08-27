package za.ac.up.cos790.selection;

import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
import za.ac.up.cos790.instrumentation.ScoreVector;
import za.ac.up.cos790.state.SearchState;

/**
 * Choice Function selection strategy (Cowling, Kendall, Soubeiga 2001).
 *
 * <p>Scores each heuristic as a weighted combination of three terms maintained in a
 * {@link ChoiceFunctionTerms} instance. The heuristic with the highest composite score
 * is selected. The weighting coefficients and term update rules are open design questions.
 *
 * <p>This class is a stub. The scoring and update logic must be implemented once the
 * design questions in {@code docs/design-decisions.md} (DD-01 and DD-07) have been
 * resolved.
 */
public final class ChoiceFunction implements SelectionStrategy {

    private ChoiceFunctionTerms terms;
    private ScoreVector lastScores;
    private int lastSelected = -1;

    /**
     * Constructs a Choice Function selector. The weighting coefficients are not yet
     * determined; see design decision DD-01.
     */
    public ChoiceFunction() {
        // TODO (DD-01): Accept weighting coefficients (alpha, beta, delta) as constructor
        //               parameters once the design has been settled.
    }

    /**
     * Selects the heuristic with the highest Choice Function score.
     *
     * @param state the current search state snapshot
     * @return index of the selected heuristic
     */
    @Override
    public int select(final SearchState state) {
        // TODO (DD-01): Implement the Choice Function scoring formula:
        //               CF(i) = alpha * f1[i] + beta * f2[last][i] + delta * f3[i]
        //               where alpha, beta, delta are learnable or fixed weights.
        //               Initialise terms on first call if heuristic count has changed.
        if (terms == null || terms.heuristicCount() != state.heuristicCount()) {
            terms = new ChoiceFunctionTerms(state.heuristicCount());
            lastScores = ScoreVector.nanVector(state.heuristicCount());
        }
        throw new UnsupportedOperationException(
                "TODO (DD-01): ChoiceFunction.select is not yet implemented. "
                + "Resolve design-decisions.md DD-01 and DD-07 first.");
    }

    /**
     * Updates the f1, f2 and f3 terms based on the observed outcome.
     *
     * @param heuristicIndex index of the heuristic that was applied
     * @param objectiveDelta change in objective value
     * @param cpuTimeMs      time consumed in milliseconds
     */
    @Override
    public void recordOutcome(final int heuristicIndex, final double objectiveDelta, final double cpuTimeMs) {
        // TODO (DD-07): Implement f1, f2, f3 update rules.
        //               f3 should increase for all heuristics not called and reset for the called one.
        //               f2 should update for the (lastSelected, heuristicIndex) pair.
        //               Decay factor and windowing strategy are open (DD-07).
    }

    /**
     * Returns the Choice Function scores assigned to all heuristics at the most recent
     * decision point.
     *
     * @return score vector (NaN entries while the strategy is not yet implemented)
     */
    @Override
    public ScoreVector scoreVector() {
        return lastScores != null ? lastScores : ScoreVector.nanVector(0);
    }
}
