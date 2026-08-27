package za.ac.up.cos790.hyperheuristic.singlepoint;

import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;
import za.ac.up.cos790.hyperheuristic.HyperHeuristicBase;
import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
import za.ac.up.cos790.state.SearchState;

import java.nio.file.Path;

/**
 * Concrete single-point hyper-heuristic that works on one solution at a time.
 *
 * <p>Delegates selection and acceptance to injected strategy objects. The depth-of-search
 * and intensity-of-mutation parameters are currently fixed stubs; their setting policy
 * is an open design question.
 */
public final class SinglePointHyperHeuristic extends HyperHeuristicBase {

    private final SelectionStrategy  selector;
    private final AcceptanceStrategy acceptor;

    /**
     * Constructs the hyper-heuristic with explicit strategy objects.
     *
     * @param seed            random seed passed to the HyFlex framework
     * @param traceOutputPath path of the CSV trace file to write
     * @param selector        the selection strategy to use
     * @param acceptor        the acceptance strategy to use
     */
    public SinglePointHyperHeuristic(
            final long seed,
            final Path traceOutputPath,
            final SelectionStrategy selector,
            final AcceptanceStrategy acceptor) {
        super(seed, traceOutputPath);
        this.selector = selector;
        this.acceptor = acceptor;
    }

    @Override
    protected SelectionStrategy selectionStrategy() {
        return selector;
    }

    @Override
    protected AcceptanceStrategy acceptanceStrategy() {
        return acceptor;
    }

    @Override
    protected double depthOfSearch(final int heuristicIndex, final SearchState state) {
        // TODO (DD-02): Decide whether dos/iom should be fixed, adaptive, or tuned per domain.
        return 0.5;
    }

    @Override
    protected double intensityOfMutation(final int heuristicIndex, final SearchState state) {
        // TODO (DD-02): As above.
        return 0.5;
    }
}
