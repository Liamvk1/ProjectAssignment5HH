package za.ac.up.cos790.experiment;

/**
 * Abstracts over time-based and iteration-based stopping criteria.
 *
 * <p>Wrapping the stopping condition in a policy object allows the search loop in
 * {@code HyperHeuristicBase} to switch between budget types without conditional
 * logic in the loop itself.
 *
 * <p>Two concrete factories are provided: {@link #timeBased(long)} and
 * {@link #iterationBased(long)}.
 */
public abstract class BudgetPolicy {

    /**
     * Returns true if the search should stop.
     *
     * @param iterationIndex zero-based iteration counter
     * @param elapsedMs      wall-clock time elapsed since the search started, in milliseconds
     * @return {@code true} when the budget is exhausted
     */
    public abstract boolean isExhausted(long iterationIndex, long elapsedMs);

    /**
     * Returns the normalised progress through the budget in the range [0.0, 1.0].
     *
     * @param iterationIndex zero-based iteration counter
     * @param elapsedMs      wall-clock time elapsed since the search started, in milliseconds
     * @return a value in [0.0, 1.0] where 1.0 means the budget is fully consumed
     */
    public abstract double progress(long iterationIndex, long elapsedMs);

    /**
     * Creates a time-based budget policy that stops after the given number of milliseconds.
     *
     * @param timeLimitMs the wall-clock time limit in milliseconds
     * @return a time-based budget policy
     */
    public static BudgetPolicy timeBased(final long timeLimitMs) {
        return new BudgetPolicy() {
            @Override
            public boolean isExhausted(final long iterationIndex, final long elapsedMs) {
                return elapsedMs >= timeLimitMs;
            }

            @Override
            public double progress(final long iterationIndex, final long elapsedMs) {
                return Math.min(1.0, (double) elapsedMs / timeLimitMs);
            }
        };
    }

    /**
     * Creates an iteration-based budget policy that stops after the given number of
     * heuristic applications.
     *
     * @param iterationLimit the maximum number of heuristic applications
     * @return an iteration-based budget policy
     */
    public static BudgetPolicy iterationBased(final long iterationLimit) {
        // TODO (DD-04): Consider whether iteration-based budgets should be preferred for
        //               reproducibility. See design-decisions.md DD-04.
        return new BudgetPolicy() {
            @Override
            public boolean isExhausted(final long iterationIndex, final long elapsedMs) {
                return iterationIndex >= iterationLimit;
            }

            @Override
            public double progress(final long iterationIndex, final long elapsedMs) {
                return Math.min(1.0, (double) iterationIndex / iterationLimit);
            }
        };
    }

    /**
     * Creates a budget policy from the type string and value found in a {@code RunConfig}.
     *
     * @param budgetType  either {@code "time"} or {@code "iterations"}
     * @param budgetValue limit in the units implied by {@code budgetType}
     * @return the appropriate budget policy
     * @throws IllegalArgumentException if {@code budgetType} is not recognised
     */
    public static BudgetPolicy fromConfig(final String budgetType, final long budgetValue) {
        return switch (budgetType.toLowerCase()) {
            case "time"       -> timeBased(budgetValue);
            case "iterations" -> iterationBased(budgetValue);
            default -> throw new IllegalArgumentException(
                    "Unknown budgetType: '" + budgetType + "'. Expected 'time' or 'iterations'.");
        };
    }
}
