package za.ac.up.cos790.hyperheuristic.singlepoint;

import za.ac.up.cos790.experiment.BudgetPolicy;
import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;
import za.ac.up.cos790.hyperheuristic.HyperHeuristicBase;
import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
import za.ac.up.cos790.state.SearchState;

import java.nio.file.Path;

/**
 * Concrete single-point hyper-heuristic that maintains one incumbent solution.
 *
 * <p>Delegates selection and acceptance to injected strategy objects so that the
 * same search loop can be compared across different strategy combinations without
 * changing this class. The multi-point comparison holds the selector constant;
 * this class is the single-point side of that comparison (Decision 22).
 *
 * <p>Depth-of-search and intensity-of-mutation are fixed at 0.1, which is the
 * HyFlex-documented default for low-level heuristics. Fixing them keeps the
 * baseline clean: any difference in outcome across selectors is attributable to
 * selection, not to a parameter that is also moving (design decision Q14).
 */
public final class SinglePointHyperHeuristic extends HyperHeuristicBase {

    private final SelectionStrategy  selector;
    private final AcceptanceStrategy acceptor;

    /**
     * Constructs the hyper-heuristic with explicit strategy objects.
     *
     * @param seed            random seed passed to the HyFlex framework
     * @param traceOutputPath path of the CSV trace file to write
     * @param budget          policy controlling budget progress and termination
     * @param selector        the selection strategy to use
     * @param acceptor        the acceptance strategy to use
     */
    public SinglePointHyperHeuristic(
            final long seed,
            final Path traceOutputPath,
            final BudgetPolicy budget,
            final SelectionStrategy  selector,
            final AcceptanceStrategy acceptor) {
        super(seed, traceOutputPath, budget);
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

    /**
     * Returns the depth-of-search parameter, fixed at 0.1.
     *
     * <p>0.1 is the HyFlex-documented default value. Holding it fixed means any
     * difference in outcome across runs is attributable to selection and acceptance,
     * not to a changing parameter (Q14).
     *
     * @param heuristicIndex unused
     * @param state          unused
     * @return 0.1
     */
    @Override
    protected double depthOfSearch(final int heuristicIndex, final SearchState state) {
        return 0.1;
    }

    /**
     * Returns the intensity-of-mutation parameter, fixed at 0.1 (Q14).
     *
     * @param heuristicIndex unused
     * @param state          unused
     * @return 0.1
     */
    @Override
    protected double intensityOfMutation(final int heuristicIndex, final SearchState state) {
        return 0.1;
    }
}
