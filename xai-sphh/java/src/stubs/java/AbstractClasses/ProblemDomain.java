package AbstractClasses;

/**
 * Compile-time stub for the HyFlex {@code ProblemDomain} abstract class.
 *
 * <p>This file is included in compilation only when the HyFlex jars are absent from
 * {@code lib/hyflex/}. It provides the API surface required to compile the project's
 * domain and hyper-heuristic classes. It does not implement any HyFlex functionality.
 *
 * <p>When the real HyFlex jars are placed in {@code lib/hyflex/}, this stub source
 * directory is excluded from the build automatically (see {@code build.gradle}).
 */
public abstract class ProblemDomain {

    /**
     * Low-level heuristic type classification used by HyFlex.
     */
    public enum HeuristicType {
        /** Applies a mutation operator to one solution. */
        MUTATION,
        /** Destroys part of a solution and rebuilds it. */
        RUIN_RECREATE,
        /** Applies a local search operator. */
        LOCAL_SEARCH,
        /** Combines two solutions to produce a child solution. */
        CROSSOVER
    }

    /** Constructs the stub. */
    protected ProblemDomain() {}

    /**
     * Generates an initial solution in the given memory slot.
     *
     * @param index solution memory slot index
     */
    public abstract void initialiseSolution(int index);

    /**
     * Returns the objective value of the solution in the given memory slot.
     *
     * @param solutionIndex solution memory slot index
     * @return objective value (lower is better for minimisation problems)
     */
    public abstract double getFunctionValue(int solutionIndex);

    /**
     * Applies a unary heuristic to the source solution and writes the result to the destination.
     *
     * @param heuristicID             index of the low-level heuristic to apply
     * @param solutionSourceIndex     source memory slot
     * @param solutionDestinationIndex destination memory slot
     * @return objective value of the resulting solution
     */
    public abstract double applyHeuristic(int heuristicID,
                                          int solutionSourceIndex,
                                          int solutionDestinationIndex);

    /**
     * Applies a binary (crossover) heuristic to two source solutions.
     *
     * @param heuristicID              index of the crossover heuristic
     * @param solutionSourceIndex1     first parent memory slot
     * @param solutionSourceIndex2     second parent memory slot
     * @param solutionDestinationIndex destination memory slot
     * @return objective value of the child solution
     */
    public abstract double applyHeuristic(int heuristicID,
                                          int solutionSourceIndex1,
                                          int solutionSourceIndex2,
                                          int solutionDestinationIndex);

    /**
     * Copies the solution in the source slot to the destination slot.
     *
     * @param source      source memory slot
     * @param destination destination memory slot
     */
    public abstract void copySolution(int source, int destination);

    /**
     * Returns the total number of low-level heuristics in this domain.
     *
     * @return heuristic count
     */
    public abstract int getNumberOfHeuristics();

    /**
     * Returns the indices of all heuristics of the given type.
     *
     * @param type heuristic type to query
     * @return array of heuristic indices, or null if none exist for this type
     */
    public abstract int[] getHeuristicsOfType(HeuristicType type);

    /**
     * Returns the type of each heuristic, indexed by heuristic index.
     *
     * @return array of heuristic types, one per heuristic
     */
    public abstract HeuristicType[] getHeuristicTypes();

    /**
     * Sets the depth-of-search parameter for the next heuristic application.
     *
     * @param depthOfSearch value in the range [0.0, 1.0]
     */
    public abstract void setDepthOfSearch(double depthOfSearch);

    /**
     * Sets the intensity-of-mutation parameter for the next heuristic application.
     *
     * @param intensityOfMutation value in the range [0.0, 1.0]
     */
    public abstract void setIntensityOfMutation(double intensityOfMutation);

    /**
     * Returns the number of available problem instances.
     *
     * @return instance count
     */
    public abstract int getNumberOfInstances();

    /**
     * Loads the problem instance at the given index.
     *
     * @param instanceIndex zero-based instance index
     */
    public abstract void loadInstance(int instanceIndex);
}
