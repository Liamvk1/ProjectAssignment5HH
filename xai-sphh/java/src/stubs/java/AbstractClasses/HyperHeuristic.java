package AbstractClasses;

/**
 * Compile-time stub for the HyFlex {@code HyperHeuristic} abstract class.
 *
 * <p>This file is included in compilation only when the HyFlex jars are absent from
 * {@code lib/hyflex/}. It provides enough of the HyFlex API surface for the project
 * to compile and for the non-HyFlex tests to run. It does not implement any HyFlex
 * functionality.
 *
 * <p>When the real HyFlex jars are placed in {@code lib/hyflex/}, this stub source
 * directory is excluded from the build automatically (see {@code build.gradle}).
 */
public abstract class HyperHeuristic {

    /** Random seed provided to the HyFlex framework. */
    protected long seed;

    /**
     * Constructs the stub with the given random seed.
     *
     * @param seed random seed
     */
    protected HyperHeuristic(final long seed) {
        this.seed = seed;
    }

    /**
     * Returns whether the configured time limit has elapsed.
     * This stub always returns true so that any accidental execution terminates immediately.
     *
     * @return true (stub implementation)
     */
    public boolean hasTimeExpired() {
        return true;
    }

    /**
     * Main search method called by the HyFlex framework.
     *
     * @param problem the problem domain to optimise
     */
    public abstract void solve(ProblemDomain problem);

    /**
     * Sets the problem domain and configures the time limit.
     * This stub is a no-op.
     *
     * @param problem the problem domain
     */
    public void loadProblemDomain(final ProblemDomain problem) {
        // Stub: no-op.
    }

    /**
     * Calls {@link #solve(ProblemDomain)} after domain setup.
     * This stub is a no-op.
     */
    public void run() {
        // Stub: no-op.
    }

    /**
     * Returns the best objective value found.
     * This stub returns {@link Double#MAX_VALUE}.
     *
     * @return stub value
     */
    public double getBestSolutionValue() {
        return Double.MAX_VALUE;
    }

    /**
     * Returns the elapsed wall-clock time in milliseconds.
     * This stub returns 0.
     *
     * @return 0 (stub)
     */
    public long getElapsedTime() {
        return 0L;
    }

    /**
     * Sets the wall-clock time limit.
     * This stub is a no-op.
     *
     * @param timeLimit time limit in milliseconds
     */
    public void setTimeLimit(final long timeLimit) {
        // Stub: no-op.
    }
}
