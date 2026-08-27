package za.ac.up.cos790.hyperheuristic;

import AbstractClasses.HyperHeuristic;
import AbstractClasses.ProblemDomain;
import za.ac.up.cos790.instrumentation.CsvTraceWriter;
import za.ac.up.cos790.instrumentation.ScoreVector;
import za.ac.up.cos790.instrumentation.TraceRecord;
import za.ac.up.cos790.instrumentation.TraceWriter;
import za.ac.up.cos790.state.FeatureExtractor;
import za.ac.up.cos790.state.SearchState;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Abstract base class for instrumented selection perturbative hyper-heuristics.
 *
 * <p>This class extends the HyFlex {@link HyperHeuristic} abstract class and implements
 * the main search loop. Subclasses supply a {@link SelectionStrategy} and an
 * {@link AcceptanceStrategy}; the base class owns the loop structure, state snapshot
 * construction, instrumentation, and trace writing.
 *
 * <p>The loop body follows this sequence:
 * <ol>
 *   <li>Snapshot the current search state.</li>
 *   <li>Ask the selection strategy for a heuristic index.</li>
 *   <li>Record the objective value before application.</li>
 *   <li>Apply the heuristic via HyFlex.</li>
 *   <li>Record the objective value after application.</li>
 *   <li>Ask the acceptance strategy whether to keep the result.</li>
 *   <li>Feed the outcome back to the selection strategy.</li>
 *   <li>Write a trace record.</li>
 * </ol>
 */
public abstract class HyperHeuristicBase extends HyperHeuristic {

    /** Solution memory slot for the current incumbent. */
    protected static final int INCUMBENT_SLOT = 0;

    /** Solution memory slot for the candidate produced by each heuristic. */
    protected static final int CANDIDATE_SLOT = 1;

    private final String runId = UUID.randomUUID().toString();
    private final Path traceOutputPath;

    /**
     * Constructs the base class with a fixed random seed and the path for the trace file.
     *
     * @param seed            the random seed, passed to the HyFlex framework
     * @param traceOutputPath path of the CSV trace file to write
     */
    protected HyperHeuristicBase(final long seed, final Path traceOutputPath) {
        super(seed);
        this.traceOutputPath = traceOutputPath;
    }

    /**
     * Returns the selection strategy that this hyper-heuristic will use.
     *
     * <p>Called once before the search loop starts.
     *
     * @return the strategy; must not be null
     */
    protected abstract SelectionStrategy selectionStrategy();

    /**
     * Returns the acceptance strategy that this hyper-heuristic will use.
     *
     * <p>Called once before the search loop starts.
     *
     * @return the strategy; must not be null
     */
    protected abstract AcceptanceStrategy acceptanceStrategy();

    /**
     * Returns the depth-of-search value to pass to HyFlex for the given heuristic.
     *
     * @param heuristicIndex the selected heuristic
     * @param state          the current search state
     * @return depth-of-search in the range [0.0, 1.0]
     */
    protected abstract double depthOfSearch(int heuristicIndex, SearchState state);

    /**
     * Returns the intensity-of-mutation value to pass to HyFlex for the given heuristic.
     *
     * @param heuristicIndex the selected heuristic
     * @param state          the current search state
     * @return intensity-of-mutation in the range [0.0, 1.0]
     */
    protected abstract double intensityOfMutation(int heuristicIndex, SearchState state);

    /**
     * Main search loop called by the HyFlex framework.
     *
     * <p>The loop continues until {@link HyperHeuristic#hasTimeExpired()} returns true.
     * This method writes one CSV row per iteration and closes the trace writer on exit.
     */
    @Override
    public void solve(final ProblemDomain problem) {
        // TODO (DD-01, DD-02): Implement the search loop body once the selection and
        //                      acceptance strategies have been designed. The structure
        //                      below is a stub showing the intended sequence of calls.
        //                      Do not implement the strategies here; delegate entirely.

        final SelectionStrategy selector   = selectionStrategy();
        final AcceptanceStrategy acceptor  = acceptanceStrategy();

        problem.initialiseSolution(INCUMBENT_SLOT);
        double bestSoFar  = problem.getFunctionValue(INCUMBENT_SLOT);
        double incumbent  = bestSoFar;
        long   iteration  = 0L;
        long   iterSinceImprovement = 0L;

        final Deque<Double>  recentDeltas   = new ArrayDeque<>(SearchState.DELTA_WINDOW);
        final Deque<Integer> heuristicHistory = new ArrayDeque<>(SearchState.HISTORY_LENGTH);

        try (final TraceWriter writer = new CsvTraceWriter(traceOutputPath)) {

            while (!hasTimeExpired()) {
                // TODO (DD-03): Build the SearchState snapshot from the live search variables.
                //               Normalise budgetProgress using the time-based budget limit.
                final SearchState state = buildState(
                        problem, iteration, incumbent, bestSoFar,
                        iterSinceImprovement, recentDeltas, heuristicHistory);

                // Step 1: selection.
                final int heuristicId = selector.select(state);
                final ScoreVector scores = selector.scoreVector();

                // Step 2: parameter setting and application.
                final double dos = depthOfSearch(heuristicId, state);
                final double iom = intensityOfMutation(heuristicId, state);
                problem.setDepthOfSearch(dos);
                problem.setIntensityOfMutation(iom);

                final double objectiveBefore = incumbent;
                final long   t0             = System.currentTimeMillis();
                problem.applyHeuristic(heuristicId, INCUMBENT_SLOT, CANDIDATE_SLOT);
                final long   t1             = System.currentTimeMillis();
                final double objectiveAfter = problem.getFunctionValue(CANDIDATE_SLOT);
                final double cpuTimeMs      = (double) (t1 - t0);

                // Step 3: acceptance.
                final boolean accepted = acceptor.accept(
                        incumbentObjective(incumbent),
                        incumbentObjective(objectiveAfter),
                        incumbentObjective(bestSoFar),
                        iteration);

                if (accepted) {
                    problem.copySolution(CANDIDATE_SLOT, INCUMBENT_SLOT);
                    incumbent = objectiveAfter;
                }
                if (objectiveAfter < bestSoFar) {
                    bestSoFar = objectiveAfter;
                    iterSinceImprovement = 0L;
                } else {
                    iterSinceImprovement++;
                }

                final double delta     = objectiveAfter - objectiveBefore;
                final double logReturn = computeLogReturn(objectiveBefore, objectiveAfter);

                // Step 4: selector feedback.
                selector.recordOutcome(heuristicId, delta, cpuTimeMs);

                // Step 5: trace record.
                final Map<String, Double> featureMap = FeatureExtractor.extract(state);
                final Map<String, Double> scoreMap   = buildScoreMap(scores);

                final TraceRecord record = new TraceRecord(
                        runId, iteration, heuristicId,
                        problem.getHeuristicTypes()[heuristicId].toString(),
                        dos, iom,
                        objectiveBefore, objectiveAfter, delta, logReturn,
                        accepted, bestSoFar, cpuTimeMs,
                        featureMap, scoreMap
                );
                writer.write(record);

                updateHistory(recentDeltas, heuristicHistory, delta, heuristicId);
                iteration++;
            }

        } catch (final IOException e) {
            throw new RuntimeException("Failed to write trace: " + traceOutputPath, e);
        }
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    private SearchState buildState(
            final ProblemDomain problem,
            final long iteration,
            final double incumbent,
            final double bestSoFar,
            final long iterSinceImprovement,
            final Deque<Double> recentDeltas,
            final Deque<Integer> heuristicHistory) {

        // TODO (DD-03): Pass the normalised budget progress once BudgetPolicy exposes it.
        final double budgetProgress = 0.0; // stub

        return new SearchState(
                problem.getNumberOfHeuristics(),
                iteration,
                budgetProgress,
                incumbent,
                bestSoFar,
                iterSinceImprovement,
                new ArrayList<>(recentDeltas),
                new ArrayList<>(heuristicHistory)
        );
    }

    private static double incumbentObjective(final double value) {
        // Minimisation is assumed throughout; return the value unchanged.
        return value;
    }

    private static double computeLogReturn(final double before, final double after) {
        // TODO (DD-08): Decide how to handle zero or negative objective values.
        if (before <= 0.0 || after <= 0.0) {
            return Double.NaN;
        }
        return Math.log(after / before);
    }

    private static Map<String, Double> buildScoreMap(final ScoreVector scores) {
        final Map<String, Double> map = new LinkedHashMap<>();
        for (int i = 0; i < scores.size(); i++) {
            map.put(String.valueOf(i), scores.get(i));
        }
        return map;
    }

    private static void updateHistory(
            final Deque<Double> recentDeltas,
            final Deque<Integer> heuristicHistory,
            final double delta,
            final int heuristicId) {

        if (recentDeltas.size() == SearchState.DELTA_WINDOW) {
            recentDeltas.pollLast();
        }
        recentDeltas.addFirst(delta);

        if (heuristicHistory.size() == SearchState.HISTORY_LENGTH) {
            heuristicHistory.pollLast();
        }
        heuristicHistory.addFirst(heuristicId);
    }
}
