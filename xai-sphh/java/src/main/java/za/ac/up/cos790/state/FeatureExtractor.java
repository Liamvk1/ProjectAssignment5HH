package za.ac.up.cos790.state;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Converts a {@link SearchState} into a named double vector for logging and analysis.
 *
 * <p><strong>Domain barrier:</strong> this is the component most likely to introduce
 * a domain-barrier violation. Every feature produced here must be derivable solely
 * from objective values, iteration counts, heuristic indices and heuristic classes.
 * Do not add features based on solution content, constraint satisfaction structure,
 * graph properties, or any other problem-specific information. The
 * {@code DomainBarrierTest} enforces this via a string deny-list.
 *
 * <p>The {@link #FEATURE_NAMES} list is published as a static constant so that the
 * Python analysis layer can assert at load time that the feature schema has not
 * drifted without a corresponding schema version bump.
 */
public final class FeatureExtractor {

    /**
     * Ordered list of feature names produced by {@link #extract(SearchState)}.
     * Every name must be free of domain-specific terms.
     * Prefixed with {@code feat_} when written to the trace file.
     */
    public static final List<String> FEATURE_NAMES = List.of(
            "heuristic_count",
            "iteration_index",
            "budget_progress",
            "current_objective",
            "best_so_far",
            "gap_to_best",
            "iterations_since_improvement",
            "recent_delta_0",
            "recent_delta_1",
            "recent_delta_2",
            "recent_delta_3",
            "recent_delta_4",
            "last_heuristic_0",
            "last_heuristic_1",
            "last_heuristic_2"
    );

    /** Utility class; no instances required. */
    private FeatureExtractor() {}

    /**
     * Extracts the feature vector from the given search state.
     *
     * <p>Returns a {@link LinkedHashMap} whose iteration order matches
     * {@link #FEATURE_NAMES}, so callers can write columns in a stable order.
     *
     * @param state the current search state snapshot
     * @return ordered map from feature name to double value
     */
    public static Map<String, Double> extract(final SearchState state) {
        // TODO (DD-03): Decide which features to enable by default and implement
        //               the extraction logic. Read enabled flags from config/features.yaml
        //               so that features can be toggled without recompiling.
        final Map<String, Double> features = new LinkedHashMap<>();

        features.put("heuristic_count",             (double) state.heuristicCount());
        features.put("iteration_index",             (double) state.iterationIndex());
        features.put("budget_progress",             state.budgetProgress());
        features.put("current_objective",           state.currentObjective());
        features.put("best_so_far",                 state.bestSoFar());
        features.put("gap_to_best",                 state.currentObjective() - state.bestSoFar());
        features.put("iterations_since_improvement",(double) state.iterationsSinceImprovement());

        // Recent objective delta window.
        final List<Double> deltas = state.recentDeltas();
        for (int i = 0; i < SearchState.DELTA_WINDOW; i++) {
            features.put("recent_delta_" + i, i < deltas.size() ? deltas.get(i) : 0.0);
        }

        // Heuristic identity history.
        final List<Integer> history = state.lastHeuristics();
        for (int i = 0; i < SearchState.HISTORY_LENGTH; i++) {
            features.put("last_heuristic_" + i, (double) (i < history.size() ? history.get(i) : -1));
        }

        return features;
    }
}
