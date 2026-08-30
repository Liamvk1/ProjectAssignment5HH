package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import za.ac.up.cos790.experiment.BudgetPolicy;
import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
import za.ac.up.cos790.hyperheuristic.multipoint.MultiPointHyperHeuristic;
import za.ac.up.cos790.instrumentation.ScoreVector;
import za.ac.up.cos790.selection.SimpleRandom;
import za.ac.up.cos790.state.SearchState;

import AbstractClasses.ProblemDomain;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Tests for {@link MultiPointHyperHeuristic}.
 *
 * <p>These tests use a minimal stub {@link ProblemDomain}. The loop terminates
 * via {@link BudgetPolicy#iterationBased(long)}, which is the primary stop condition
 * in {@code MultiPointHyperHeuristic.solve()}.
 */
class MultiPointHyperHeuristicTest {

    /**
     * Minimal stub ProblemDomain. Stores objectives in a slot array.
     * Implements the full real HyFlex ProblemDomain abstract API.
     */
    private static final class StubDomain extends ProblemDomain {

        private final double[] slots;
        private double nextObjective;
        private int    applicationCount = 0;

        StubDomain(final int memorySlots, final double initial) {
            super(0L); // ProblemDomain(long seed) — required by real HyFlex API.
            this.slots        = new double[memorySlots];
            this.nextObjective = initial;
            Arrays.fill(this.slots, initial);
        }

        void setNextObjective(final double v) {
            this.nextObjective = v;
        }

        int applicationCount() {
            return applicationCount;
        }

        @Override public void   initialiseSolution(final int i)   { slots[i] = nextObjective; }
        @Override public double getFunctionValue(final int i)      { return slots[i]; }
        @Override public double applyHeuristic(final int h, final int src, final int dst) {
            applicationCount++;
            slots[dst] = nextObjective;
            return nextObjective;
        }
        @Override public double applyHeuristic(final int h, final int s1, final int s2, final int d) {
            applicationCount++;
            slots[d] = nextObjective;
            return nextObjective;
        }
        @Override public void   copySolution(final int src, final int dst) { slots[dst] = slots[src]; }
        @Override public int    getNumberOfHeuristics()                    { return 3; }
        @Override public int[]  getHeuristicsOfType(final HeuristicType t) {
            return (t == HeuristicType.MUTATION) ? new int[]{0, 1, 2} : new int[0];
        }
        @Override public int[]  getHeuristicsThatUseDepthOfSearch()        { return new int[0]; }
        @Override public int[]  getHeuristicsThatUseIntensityOfMutation()  { return new int[0]; }
        @Override public int    getNumberOfInstances()                      { return 1; }
        @Override public void   loadInstance(final int i)                   {}
        @Override public void   setMemorySize(final int size)               {}
        @Override public boolean compareSolutions(final int a, final int b) { return slots[a] == slots[b]; }
        @Override public String  bestSolutionToString()                      { return "stub-best"; }
        @Override public double  getBestSolutionValue()                      { return nextObjective; }
        @Override public String  solutionToString(final int i)              { return "stub-" + i; }
        @Override public String  toString()                                  { return "StubDomain"; }
    }

    /** A SelectionStrategy that always picks heuristic 0. */
    private static final class ConstantSelector implements SelectionStrategy {
        private int n = 3;
        @Override public int select(final SearchState s) { this.n = s.heuristicCount(); return 0; }
        @Override public void recordOutcome(final int h, final double d, final double ms) {}
        @Override public ScoreVector scoreVector() { return ScoreVector.nanVector(n); }
    }

    /**
     * Elitism: the population best must never be replaced by a worse individual.
     * We run with a fixed improving objective so every candidate is better, then
     * check that the trace was produced.
     */
    @Test
    void elitismTraceProducedForImprovingRun() throws IOException {
        final int  pop        = 4;
        final int  iterations = 50;
        final Path traceFile  = Files.createTempFile("mphh_elitism_", ".csv");

        final StubDomain domain = new StubDomain(pop + 1, 100.0);
        domain.setNextObjective(80.0); // every application improves

        try {
            final MultiPointHyperHeuristic mphh = new MultiPointHyperHeuristic(
                    42L, traceFile,
                    BudgetPolicy.iterationBased(iterations),
                    new ConstantSelector(), pop);
            mphh.setTimeLimit(300_000L); // required by real HyFlex before loadProblemDomain
            mphh.loadProblemDomain(domain);
            mphh.run();

            assertTrue(traceFile.toFile().exists(), "Trace file must be created.");
            assertTrue(traceFile.toFile().length() > 0, "Trace file must not be empty.");
        } finally {
            Files.deleteIfExists(traceFile);
        }
    }

    /**
     * One trace record must be emitted per heuristic application, including
     * non-improving ones. We run with a worsening objective (no replacements occur)
     * and count CSV data rows.
     */
    @Test
    void oneRecordPerApplicationIncludingNonImproving() throws IOException {
        final int  pop        = 3;
        final int  iterations = 20;
        final Path traceFile  = Files.createTempFile("mphh_count_", ".csv");

        final StubDomain domain = new StubDomain(pop + 1, 100.0);
        domain.setNextObjective(200.0); // worsening: no replacements

        try {
            final MultiPointHyperHeuristic mphh = new MultiPointHyperHeuristic(
                    7L, traceFile,
                    BudgetPolicy.iterationBased(iterations),
                    new ConstantSelector(), pop);
            mphh.setTimeLimit(300_000L); // required by real HyFlex before loadProblemDomain
            mphh.loadProblemDomain(domain);
            mphh.run();

            // Count rows: total lines minus 1 header row.
            final long dataRows = Files.lines(traceFile).count() - 1;
            assertTrue(dataRows >= iterations,
                    "Must have at least " + iterations + " data rows; got " + dataRows + ".");
        } finally {
            Files.deleteIfExists(traceFile);
        }
    }

    /**
     * The constructor must accept no AcceptanceStrategy argument.
     */
    @Test
    void constructorTakesNoAcceptanceStrategy() throws IOException {
        final Path traceFile = Files.createTempFile("mphh_construct_", ".csv");
        try {
            final MultiPointHyperHeuristic mphh = new MultiPointHyperHeuristic(
                    1L, traceFile,
                    BudgetPolicy.iterationBased(0L),
                    new SimpleRandom(1L));
            assertFalse(mphh == null, "Constructor must succeed.");
        } finally {
            Files.deleteIfExists(traceFile);
        }
    }
}
