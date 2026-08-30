package za.ac.up.cos790.hyperheuristic.multipoint;

import AbstractClasses.HyperHeuristic;
import AbstractClasses.ProblemDomain;
import za.ac.up.cos790.experiment.BudgetPolicy;
import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
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
import java.util.Random;
import java.util.UUID;

/**
 * Population-based selection perturbative hyper-heuristic (steady-state multi-point).
 *
 * <p>This class does NOT use an {@link za.ac.up.cos790.hyperheuristic.AcceptanceStrategy}.
 * In population-based search, acceptance is expressed through the replacement rule:
 * the candidate replaces its target individual when it is strictly better. This
 * design decision is explicit so that the correspondence with the single-point technique
 * (where acceptance is a separate component) is clear to a reader (Decision 25).
 *
 * <p>Population protocol (Decision 22):
 * <ul>
 *   <li>Population size: {@value #DEFAULT_POPULATION_SIZE}, configurable.</li>
 *   <li>Target selection: binary tournament, two distinct individuals drawn at random;
 *       the worse one is selected as the target to maximise replacement benefit.</li>
 *   <li>Second crossover parent: binary tournament excluding the target index.</li>
 *   <li>Replacement: replace the target only when the candidate is strictly better.</li>
 *   <li>Elitism: the population-best slot is never overwritten; this is checked before
 *       the write, not repaired afterwards.</li>
 * </ul>
 *
 * <p>The selector is shared globally across the population, not held per individual.
 * This is deliberate: the experiment compares single-point against multi-point search
 * while holding the selector constant. Per-individual selectors would measure
 * two unrelated systems (Decision 22).
 *
 * <p>Solution memory layout:
 * <ul>
 *   <li>Slots 0..popSize-1: population individuals.</li>
 *   <li>Slot popSize: candidate produced at each step.</li>
 * </ul>
 */
public class MultiPointHyperHeuristic extends HyperHeuristic {

    /** Default population size (Decision 22). */
    public static final int DEFAULT_POPULATION_SIZE = 10;

    /** Depth-of-search fixed at 0.1, the HyFlex-documented default (Q14). */
    private static final double DEPTH_OF_SEARCH = 0.1;

    /** Intensity-of-mutation fixed at 0.1, the HyFlex-documented default (Q14). */
    private static final double INTENSITY_OF_MUTATION = 0.1;

    private final int              populationSize;
    private final SelectionStrategy selector;
    private final BudgetPolicy     budget;
    private final Path             traceOutputPath;
    private final String           runId = UUID.randomUUID().toString();
    private final Random           rng;

    /**
     * Constructs a multi-point hyper-heuristic with the default population size.
     *
     * @param seed            random seed for population management and tie-breaking
     * @param traceOutputPath path of the CSV trace file to write
     * @param budget          budget policy for progress calculation
     * @param selector        shared selection strategy (global across population)
     */
    public MultiPointHyperHeuristic(final long seed,
                                     final Path traceOutputPath,
                                     final BudgetPolicy budget,
                                     final SelectionStrategy selector) {
        this(seed, traceOutputPath, budget, selector, DEFAULT_POPULATION_SIZE);
    }

    /**
     * Constructs a multi-point hyper-heuristic with the given population size.
     *
     * @param seed            random seed
     * @param traceOutputPath path of the CSV trace file
     * @param budget          budget policy
     * @param selector        shared selection strategy
     * @param populationSize  number of individuals to maintain
     */
    public MultiPointHyperHeuristic(final long seed,
                                     final Path traceOutputPath,
                                     final BudgetPolicy budget,
                                     final SelectionStrategy selector,
                                     final int populationSize) {
        super(seed);
        this.traceOutputPath = traceOutputPath;
        this.budget          = budget;
        this.selector        = selector;
        this.populationSize  = populationSize;
        this.rng             = new Random(seed + 1L); // distinct stream from selector seed
    }

    /**
     * Main search loop.
     *
     * <p>Each iteration: select a target individual by binary tournament, apply a
     * heuristic selected by the shared selector, replace the target if the candidate
     * is strictly better (the elitism guard is checked before the write). One trace
     * record is written for every application regardless of whether it improved.
     *
     * <p>The {@code accepted} column is populated from the replacement outcome.
     */
    /** Returns the class name as the human-readable identifier for this hyper-heuristic. */
    @Override
    public String toString() {
        return getClass().getSimpleName();
    }

    @Override
    protected void solve(final ProblemDomain problem) {
        final int candidateSlot = populationSize;

        // Allocate memory for all population slots plus the candidate slot.
        problem.setMemorySize(populationSize + 1);

        // Build heuristic-index → HeuristicType lookup (real HyFlex API has no getHeuristicTypes()).
        final ProblemDomain.HeuristicType[] heuristicTypes = resolveHeuristicTypes(problem);

        // Initialise all population slots.
        double[] popObjectives = new double[populationSize];
        for (int i = 0; i < populationSize; i++) {
            problem.initialiseSolution(i);
            popObjectives[i] = problem.getFunctionValue(i);
        }

        // Identify the initial population best.
        int    bestSlot   = argminSlot(popObjectives);
        double bestSoFar  = popObjectives[bestSlot];

        // Running extrema for feature normalisation.
        double runningMin = bestSoFar;
        double runningMax = maxValue(popObjectives);

        long iteration        = 0L;
        long iterSinceImprove = 0L;
        long iterSinceAccept  = 0L;
        final long startMs    = System.currentTimeMillis();

        final Deque<Double>  recentDeltas     = new ArrayDeque<>(SearchState.WINDOW_SIZE);
        final Deque<Double>  recentLogReturns = new ArrayDeque<>(SearchState.WINDOW_SIZE);
        final Deque<Integer> heuristicHistory = new ArrayDeque<>(SearchState.HISTORY_LENGTH);
        final Deque<Integer> classHistory     = new ArrayDeque<>(SearchState.HISTORY_LENGTH);

        try (final TraceWriter writer = new CsvTraceWriter(traceOutputPath)) {

            long elapsedMs = 0L;
            while (!budget.isExhausted(iteration, elapsedMs)) {
                elapsedMs = System.currentTimeMillis() - startMs;
                final double budgetProgress = budget.progress(iteration, elapsedMs);

                // Target selection: binary tournament; pick the worse of two random individuals.
                final int targetIndex  = binaryTournamentTarget(popObjectives);
                final double incumbent = popObjectives[targetIndex];

                // Population statistics for features (Decision 28).
                final double popBest  = popObjectives[bestSlot];
                final double popMean  = mean(popObjectives);
                final double popDiv   = diversity(popObjectives, popMean);
                final int    targetRank = rankOf(targetIndex, popObjectives);

                // Build state snapshot.
                final SearchState state = new SearchState(
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
                        new ArrayList<>(classHistory),
                        popBest, popMean, popDiv, targetRank
                );

                // Selection.
                final int         heuristicId = selector.select(state);
                final ScoreVector scores      = selector.scoreVector();

                final String heuristicClass = heuristicTypes[heuristicId].toString();
                final int    classOrdinal   = heuristicTypes[heuristicId].ordinal();

                problem.setDepthOfSearch(DEPTH_OF_SEARCH);
                problem.setIntensityOfMutation(INTENSITY_OF_MUTATION);

                // Select second parent for crossover heuristics.
                int secondParentIndex = -1;
                final double objectiveBefore = incumbent;
                final long   t0             = System.currentTimeMillis();
                final double objectiveAfter;

                if (isCrossover(heuristicTypes, heuristicId)) {
                    secondParentIndex = binaryTournamentExcluding(popObjectives, targetIndex);
                    objectiveAfter = problem.applyHeuristic(
                            heuristicId, targetIndex, secondParentIndex, candidateSlot);
                } else {
                    objectiveAfter = problem.applyHeuristic(
                            heuristicId, targetIndex, candidateSlot);
                }
                final long   t1        = System.currentTimeMillis();
                final double cpuTimeMs = (double) (t1 - t0);

                final double delta     = objectiveAfter - objectiveBefore;
                final double logReturn = computeLogReturn(objectiveBefore, objectiveAfter);

                // Update best-so-far from the candidate even before the replacement check.
                if (objectiveAfter < bestSoFar) {
                    bestSoFar        = objectiveAfter;
                    iterSinceImprove = 0L;
                } else {
                    iterSinceImprove++;
                }

                // Update running extrema.
                runningMin = Math.min(runningMin, objectiveAfter);
                runningMax = Math.max(runningMax, objectiveAfter);

                // Replacement rule: replace the target only when the candidate is strictly
                // better AND the target is not the population-best slot.
                // Elitism: the best slot is never overwritten (Decision 22).
                final boolean accepted;
                if (objectiveAfter < popObjectives[targetIndex]
                        && targetIndex != bestSlot) {
                    problem.copySolution(candidateSlot, targetIndex);
                    popObjectives[targetIndex] = objectiveAfter;
                    accepted      = true;
                    iterSinceAccept = 0L;

                    // Re-identify the population best after replacement.
                    bestSlot = argminSlot(popObjectives);
                } else {
                    accepted = false;
                    iterSinceAccept++;
                }

                // Selector feedback.
                selector.recordOutcome(heuristicId, delta, cpuTimeMs);

                // Trace record.
                final Map<String, Double> featureMap = FeatureExtractor.extract(state);
                final Map<String, Double> scoreMap   = buildScoreMap(scores);

                final TraceRecord record = new TraceRecord(
                        runId, iteration, heuristicId, heuristicClass,
                        DEPTH_OF_SEARCH, INTENSITY_OF_MUTATION,
                        targetIndex, targetIndex, secondParentIndex,
                        objectiveBefore, objectiveAfter, delta, logReturn,
                        accepted, bestSoFar, cpuTimeMs,
                        popObjectives[bestSlot], mean(popObjectives), diversity(popObjectives, mean(popObjectives)),
                        featureMap, scoreMap
                );
                writer.write(record);

                pushWindow(recentDeltas,     SearchState.WINDOW_SIZE,    delta);
                pushWindow(recentLogReturns, SearchState.WINDOW_SIZE,    logReturn);
                pushHistory(heuristicHistory, SearchState.HISTORY_LENGTH, heuristicId);
                pushHistory(classHistory,     SearchState.HISTORY_LENGTH, classOrdinal);

                iteration++;
            }

        } catch (final IOException e) {
            throw new RuntimeException("Failed to write trace: " + traceOutputPath, e);
        }
    }

    // -------------------------------------------------------------------------
    // Population helpers
    // -------------------------------------------------------------------------

    /** Returns the slot index with the minimum objective. */
    private static int argminSlot(final double[] objectives) {
        int best = 0;
        for (int i = 1; i < objectives.length; i++) {
            if (objectives[i] < objectives[best]) {
                best = i;
            }
        }
        return best;
    }

    /** Returns the maximum value in the array. */
    private static double maxValue(final double[] objectives) {
        double max = objectives[0];
        for (int i = 1; i < objectives.length; i++) {
            if (objectives[i] > max) {
                max = objectives[i];
            }
        }
        return max;
    }

    /** Returns the mean of the array. */
    private static double mean(final double[] objectives) {
        double sum = 0.0;
        for (final double v : objectives) {
            sum += v;
        }
        return sum / objectives.length;
    }

    /**
     * Returns the coefficient of variation: standard deviation divided by mean.
     * Returns NaN when the mean is zero.
     */
    private static double diversity(final double[] objectives, final double mu) {
        if (mu == 0.0) {
            return Double.NaN;
        }
        double variance = 0.0;
        for (final double v : objectives) {
            final double diff = v - mu;
            variance += diff * diff;
        }
        return Math.sqrt(variance / objectives.length) / mu;
    }

    /**
     * Returns the rank (0 = best) of the given slot within the population.
     */
    private static int rankOf(final int slotIndex, final double[] objectives) {
        int rank = 0;
        for (int i = 0; i < objectives.length; i++) {
            if (i != slotIndex && objectives[i] < objectives[slotIndex]) {
                rank++;
            }
        }
        return rank;
    }

    /**
     * Binary tournament selection: draws two distinct individuals at random and
     * returns the index of the worse one (higher objective for minimisation).
     * Choosing the worse target maximises replacement benefit.
     */
    private int binaryTournamentTarget(final double[] objectives) {
        final int a = rng.nextInt(populationSize);
        int b = rng.nextInt(populationSize - 1);
        if (b >= a) {
            b++;
        }
        // Return the worse (higher objective) individual as the target.
        return (objectives[a] >= objectives[b]) ? a : b;
    }

    /**
     * Binary tournament selection excluding a given slot.
     */
    private int binaryTournamentExcluding(final double[] objectives, final int exclude) {
        // Build candidate set without the excluded index.
        final int effectiveSize = populationSize - 1;
        final int rawA = rng.nextInt(effectiveSize);
        final int a    = (rawA >= exclude) ? rawA + 1 : rawA;
        int rawB = rng.nextInt(effectiveSize - 1);
        if (rawB >= Math.min(rawA, effectiveSize - 1)) {
            rawB++;
        }
        final int b = (rawB >= exclude) ? rawB + 1 : rawB;
        return (objectives[a] <= objectives[b]) ? a : b;
    }

    /**
     * Returns true when the given heuristic index is a crossover heuristic.
     * Uses the pre-built type array rather than querying the domain each call.
     */
    private static boolean isCrossover(
            final ProblemDomain.HeuristicType[] types, final int heuristicId) {
        return types[heuristicId] == ProblemDomain.HeuristicType.CROSSOVER;
    }

    /**
     * Builds a heuristic-index to {@link ProblemDomain.HeuristicType} lookup array.
     * The real HyFlex {@code ProblemDomain} has {@code getHeuristicsOfType(type)} but not
     * {@code getHeuristicTypes()}. This helper inverts the per-type index lists.
     */
    private static ProblemDomain.HeuristicType[] resolveHeuristicTypes(
            final ProblemDomain problem) {
        final int n = problem.getNumberOfHeuristics();
        final ProblemDomain.HeuristicType[] types = new ProblemDomain.HeuristicType[n];
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

    /**
     * Computes log return; returns NaN for non-positive objectives (DD-08).
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

    private static void pushWindow(final Deque<Double> deque, final int max, final double val) {
        if (deque.size() == max) {
            deque.pollLast();
        }
        deque.addFirst(val);
    }

    private static void pushHistory(final Deque<Integer> deque, final int max, final int val) {
        if (deque.size() == max) {
            deque.pollLast();
        }
        deque.addFirst(val);
    }
}
