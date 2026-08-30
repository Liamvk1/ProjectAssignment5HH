package za.ac.up.cos790.hyperheuristic;

import AbstractClasses.HyperHeuristic;
import AbstractClasses.ProblemDomain;
import za.ac.up.cos790.experiment.BudgetPolicy;
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
import java.util.Map;
import java.util.UUID;

/**
 * Abstract base class for instrumented single-point selection perturbative hyper-heuristics.
 *
 * <p>This class extends the HyFlex {@link HyperHeuristic} abstract class and implements
 * the main search loop. Subclasses supply a {@link SelectionStrategy} and an
 * {@link AcceptanceStrategy}; the base class owns the loop structure, state snapshot
 * construction, instrumentation, and trace writing.
 *
 * <p>Solution memory layout (Q20):
 * <ul>
 *   <li>Slot 0 ({@link #INCUMBENT_SLOT}): current working solution.</li>
 *   <li>Slot 1 ({@link #CANDIDATE_SLOT}): candidate produced at each step.</li>
 *   <li>Slot 2 ({@link #BEST_SO_FAR_SLOT}): best solution seen across the run.
 *       Updated from the candidate even when acceptance rejects that candidate.</li>
 * </ul>
 *
 * <p>The loop body follows this sequence:
 * <ol>
 *   <li>Snapshot the current search state.</li>
 *   <li>Ask the selection strategy for a heuristic index.</li>
 *   <li>Record the objective before application.</li>
 *   <li>Apply the heuristic via HyFlex (incumbent to candidate).</li>
 *   <li>Record the objective after application.</li>
 *   <li>Update best-so-far from the candidate (even if acceptance rejects it).</li>
 *   <li>Ask the acceptance strategy whether to keep the candidate.</li>
 *   <li>Feed the outcome back to the selection strategy.</li>
 *   <li>Write a trace record.</li>
 * </ol>
 *
 * <p>At the end of the run the best-so-far solution is copied into the incumbent
 * slot so that HyFlex scores the best solution found, not the one held at timeout.
 */
public abstract class HyperHeuristicBase extends HyperHeuristic {

    /** Solution memory slot for the current incumbent. */
    protected static final int INCUMBENT_SLOT     = 0;

    /** Solution memory slot for the candidate produced by each heuristic. */
    protected static final int CANDIDATE_SLOT     = 1;

    /**
     * Solution memory slot for the best solution seen.
     * Updated from the candidate at every step; slots 3+ belong to second-parent policies.
     */
    protected static final int BEST_SO_FAR_SLOT   = 2;

    private final String       runId            = UUID.randomUUID().toString();
    private final Path         traceOutputPath;
    private final BudgetPolicy budget;

    /**
     * Constructs the base class with a fixed seed, trace path, and budget policy.
     *
     * @param seed            random seed passed to the HyFlex framework
     * @param traceOutputPath path of the CSV trace file to write
     * @param budget          policy controlling budget progress calculation
     */
    protected HyperHeuristicBase(final long seed,
                                  final Path traceOutputPath,
                                  final BudgetPolicy budget) {
        super(seed);
        this.traceOutputPath = traceOutputPath;
        this.budget          = budget;
    }

    /** Returns the selection strategy. Called once before the search loop starts. */
    protected abstract SelectionStrategy selectionStrategy();

    /** Returns the acceptance strategy. Called once before the search loop starts. */
    protected abstract AcceptanceStrategy acceptanceStrategy();

    /**
     * Returns the depth-of-search value to pass to HyFlex for the given heuristic.
     *
     * @param heuristicIndex the selected heuristic
     * @param state          current search state
     * @return depth-of-search in [0.0, 1.0]
     */
    protected abstract double depthOfSearch(int heuristicIndex, SearchState state);

    /**
     * Returns the intensity-of-mutation value to pass to HyFlex for the given heuristic.
     *
     * @param heuristicIndex the selected heuristic
     * @param state          current search state
     * @return intensity-of-mutation in [0.0, 1.0]
     */
    protected abstract double intensityOfMutation(int heuristicIndex, SearchState state);

    /**
     * Main search loop called by the HyFlex framework.
     *
     * <p>Continues until {@link HyperHeuristic#hasTimeExpired()} returns true.
     * Writes one CSV row per iteration. The best-so-far solution is copied back to
     * the incumbent slot on exit.
     */
    /** Returns the class name as the human-readable identifier for this hyper-heuristic. */
    @Override
    public String toString() {
        return getClass().getSimpleName();
    }

    @Override
    protected void solve(final ProblemDomain problem) {
        // Enlarge the solution memory to hold incumbent, candidate, and best-so-far.
        problem.setMemorySize(3);

        // Build a heuristic-index → HeuristicType lookup from the real HyFlex API.
        // The real ProblemDomain exposes getHeuristicsOfType(type) not getHeuristicTypes().
        final ProblemDomain.HeuristicType[] heuristicTypes = resolveHeuristicTypes(problem);

        final SelectionStrategy  selector = selectionStrategy();
        final AcceptanceStrategy acceptor = acceptanceStrategy();

        problem.initialiseSolution(INCUMBENT_SLOT);
        double incumbent    = problem.getFunctionValue(INCUMBENT_SLOT);
        double bestSoFar    = incumbent;
        problem.copySolution(INCUMBENT_SLOT, BEST_SO_FAR_SLOT);

        // Running objective range for normalisation. Using running extrema only;
        // using the full-run range would leak future information into decision-time
        // features and inflate surrogate accuracy for the wrong reason (Decision 28).
        double runningMin = incumbent;
        double runningMax = incumbent;

        long iteration           = 0L;
        long iterSinceImprove    = 0L;
        long iterSinceAccept     = 0L;
        final long searchStartMs = System.currentTimeMillis();

        final Deque<Double>  recentDeltas     = new ArrayDeque<>(SearchState.WINDOW_SIZE);
        final Deque<Double>  recentLogReturns = new ArrayDeque<>(SearchState.WINDOW_SIZE);
        final Deque<Integer> heuristicHistory = new ArrayDeque<>(SearchState.HISTORY_LENGTH);
        final Deque<Integer> classHistory     = new ArrayDeque<>(SearchState.HISTORY_LENGTH);

        try (final TraceWriter writer = new CsvTraceWriter(traceOutputPath)) {

            long elapsedMs = 0L;
            while (!budget.isExhausted(iteration, elapsedMs)) {
                elapsedMs = System.currentTimeMillis() - searchStartMs;
                final double budgetProgress = budget.progress(iteration, elapsedMs);

                final SearchState state = SearchState.singlePoint(
                        problem.getNumberOfHeuristics(),
                        iteration,
                        budgetProgress,
                        incumbent,
                        bestSoFar,
                        iterSinceImprove,
                        iterSinceAccept,
                        runningMin,
                        runningMax,
                        new ArrayList<>(recentDeltas),
                        new ArrayList<>(recentLogReturns),
                        new ArrayList<>(heuristicHistory),
                        new ArrayList<>(classHistory)
                );

                // Selection.
                final int         heuristicId = selector.select(state);
                final ScoreVector scores      = selector.scoreVector();

                // Parameter setting.
                final double dos = depthOfSearch(heuristicId, state);
                final double iom = intensityOfMutation(heuristicId, state);
                problem.setDepthOfSearch(dos);
                problem.setIntensityOfMutation(iom);

                // Application: measure CPU time around applyHeuristic only,
                // excluding logging and feature extraction overhead (Decision 24).
                final double objectiveBefore = incumbent;
                final long   t0             = System.currentTimeMillis();
                problem.applyHeuristic(heuristicId, INCUMBENT_SLOT, CANDIDATE_SLOT);
                final long   t1             = System.currentTimeMillis();
                final double objectiveAfter = problem.getFunctionValue(CANDIDATE_SLOT);
                final double cpuTimeMs      = (double) (t1 - t0);

                final double delta     = objectiveAfter - objectiveBefore;
                final double logReturn = computeLogReturn(objectiveBefore, objectiveAfter);

                // Update best-so-far from the candidate BEFORE the acceptance decision.
                // The candidate can be the best solution of the whole run and still be
                // rejected by the acceptance criterion (Q20).
                if (objectiveAfter < bestSoFar) {
                    bestSoFar = objectiveAfter;
                    iterSinceImprove = 0L;
                    problem.copySolution(CANDIDATE_SLOT, BEST_SO_FAR_SLOT);
                } else {
                    iterSinceImprove++;
                }

                // Update running extrema for normalisation (running values only).
                runningMin = Math.min(runningMin, objectiveAfter);
                runningMax = Math.max(runningMax, objectiveAfter);

                // Acceptance decision.
                final boolean accepted = acceptor.accept(
                        incumbent, objectiveAfter, bestSoFar, iteration);

                if (accepted) {
                    problem.copySolution(CANDIDATE_SLOT, INCUMBENT_SLOT);
                    incumbent     = objectiveAfter;
                    iterSinceAccept = 0L;
                } else {
                    iterSinceAccept++;
                }

                // Selector feedback.
                selector.recordOutcome(heuristicId, delta, cpuTimeMs);

                // Determine heuristic class for the trace and class history.
                final String heuristicClass = heuristicTypes[heuristicId].toString();
                final int    classOrdinal   = heuristicTypes[heuristicId].ordinal();

                // Build the trace record.
                final Map<String, Double> featureMap = FeatureExtractor.extract(state);
                final Map<String, Double> scoreMap   = buildScoreMap(scores);

                final TraceRecord record = new TraceRecord(
                        runId, iteration, heuristicId, heuristicClass,
                        dos, iom,
                        INCUMBENT_SLOT, INCUMBENT_SLOT, -1,
                        objectiveBefore, objectiveAfter, delta, logReturn,
                        accepted, bestSoFar, cpuTimeMs,
                        bestSoFar, objectiveBefore, 0.0,
                        featureMap, scoreMap
                );
                writer.write(record);

                // Advance history windows.
                pushWindow(recentDeltas,     SearchState.WINDOW_SIZE,    delta);
                pushWindow(recentLogReturns, SearchState.WINDOW_SIZE,    logReturn);
                pushHistory(heuristicHistory, SearchState.HISTORY_LENGTH, heuristicId);
                pushHistory(classHistory,     SearchState.HISTORY_LENGTH, classOrdinal);

                iteration++;
            }

        } catch (final IOException e) {
            throw new RuntimeException("Failed to write trace: " + traceOutputPath, e);
        }

        // Copy the best solution into the incumbent slot so HyFlex scores the
        // best-found result, not whatever was held when the budget expired (Q20).
        problem.copySolution(BEST_SO_FAR_SLOT, INCUMBENT_SLOT);
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    /**
     * Computes the log return. Returns NaN when either value is non-positive,
     * which the CSV writer translates to an empty field (DD-08).
     */
    private static double computeLogReturn(final double before, final double after) {
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

    private static void pushWindow(final Deque<Double> deque, final int maxSize, final double value) {
        if (deque.size() == maxSize) {
            deque.pollLast();
        }
        deque.addFirst(value);
    }

    private static void pushHistory(final Deque<Integer> deque, final int maxSize, final int value) {
        if (deque.size() == maxSize) {
            deque.pollLast();
        }
        deque.addFirst(value);
    }

    /**
     * Builds a heuristic-index to {@link ProblemDomain.HeuristicType} lookup array using
     * the real HyFlex API ({@code getHeuristicsOfType}). The real {@code ProblemDomain}
     * does not expose a {@code getHeuristicTypes()} method; this helper provides the
     * equivalent mapping by inverting the per-type index lists.
     */
    private static ProblemDomain.HeuristicType[] resolveHeuristicTypes(
            final ProblemDomain problem) {
        final int n = problem.getNumberOfHeuristics();
        final ProblemDomain.HeuristicType[] types =
                new ProblemDomain.HeuristicType[n];
        // Default every slot to MUTATION so no entry is null.
        java.util.Arrays.fill(types, ProblemDomain.HeuristicType.MUTATION);
        for (final ProblemDomain.HeuristicType t : ProblemDomain.HeuristicType.values()) {
            final int[] indices = problem.getHeuristicsOfType(t);
            if (indices != null) {
                for (final int idx : indices) {
                    if (idx >= 0 && idx < n) {
                        types[idx] = t;
                    }
                }
            }
        }
        return types;
    }
}
