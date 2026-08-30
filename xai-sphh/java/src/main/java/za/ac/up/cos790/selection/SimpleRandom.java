package za.ac.up.cos790.selection;

import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
import za.ac.up.cos790.instrumentation.ScoreVector;
import za.ac.up.cos790.state.SearchState;

import java.util.Random;

/**
 * Selection strategy that chooses a heuristic uniformly at random.
 *
 * <p>This is the simplest possible selection strategy and serves as the experimental
 * baseline. It maintains no internal state and returns a NaN score vector because
 * it assigns no meaningful score to any heuristic.
 */
public final class SimpleRandom implements SelectionStrategy {

    private final Random rng;
    private int heuristicCount = 0;

    /**
     * Constructs a random selector with the given seed.
     *
     * @param seed random seed for reproducibility
     */
    public SimpleRandom(final long seed) {
        this.rng = new Random(seed);
    }

    /**
     * Selects a heuristic index uniformly at random from the available heuristics.
     *
     * @param state the current search state snapshot
     * @return a random heuristic index in the range [0, heuristicCount)
     */
    @Override
    public int select(final SearchState state) {
        this.heuristicCount = state.heuristicCount();
        return rng.nextInt(state.heuristicCount());
    }

    /**
     * Receives outcome feedback; this strategy ignores it.
     *
     * @param heuristicIndex index of the heuristic that was applied
     * @param objectiveDelta change in objective value
     * @param cpuTimeMs      time consumed in milliseconds
     */
    @Override
    public void recordOutcome(final int heuristicIndex, final double objectiveDelta, final double cpuTimeMs) {
        // SimpleRandom does not update on feedback. No state to maintain.
    }

    /**
     * Returns a NaN score vector because this strategy assigns no meaningful scores.
     *
     * @return all-NaN score vector of length equal to the heuristic count
     */
    @Override
    public ScoreVector scoreVector() {
        return ScoreVector.nanVector(heuristicCount);
    }
}
