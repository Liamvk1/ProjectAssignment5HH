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
 *
 * <p>Feature set matches Decision 28 (Member 1+3) and DD-03 (Member 4).
 */
public final class FeatureExtractor {

    /**
     * Ordered list of feature names produced by {@link #extract(SearchState)}.
     * Written to the trace with the prefix {@code feat_}.
     * Every name must be free of domain-specific terms (enforced by DomainBarrierTest).
     */
    public static final List<String> FEATURE_NAMES = List.of(
            "llh_count",
            "progress",
            "obj_norm",
            "gap_to_best",
            "iters_since_improve",
            "improve_rate_50",
            "mean_logret_50",
            "last_h1",
            "last_h2",
            "last_h3",
            "last_class1",
            "last_class2",
            "last_class3",
            "iters_since_accept",
            "pop_diversity",
            "pop_target_rank"
    );

    /** Small epsilon used to avoid division by zero in objective normalisation. */
    private static final double RANGE_FLOOR = 1e-10;

    /** Utility class; no instances required. */
    private FeatureExtractor() {}

    /**
     * Extracts the feature vector from the given search state.
     *
     * <p>Returns a {@link LinkedHashMap} whose iteration order matches
     * {@link #FEATURE_NAMES}, so callers can write columns in a stable order.
     *
     * <p><strong>Normalisation note:</strong> {@code obj_norm} and {@code gap_to_best}
     * are scaled against the running observed range ({@link SearchState#runningMin()}
     * to {@link SearchState#runningMax()}). They must never be scaled against the
     * full-run range because doing so leaks future information into a decision-time
     * feature and inflates surrogate model accuracy for the wrong reason (Decision 28).
     *
     * <p><strong>Categorical note:</strong> {@code last_h*} and {@code last_class*}
     * are heuristic identifiers written as integers. They are categorical, not ordinal;
     * declare them as categorical in the analysis layer. The sentinel value -1 is used
     * for steps where no predecessor exists, rather than 0, which is a valid index.
     *
     * @param state the current search state snapshot
     * @return ordered map from feature name (without prefix) to double value
     */
    public static Map<String, Double> extract(final SearchState state) {
        final Map<String, Double> features = new LinkedHashMap<>();

        // Number of low-level heuristics available in the domain.
        features.put("llh_count", (double) state.heuristicCount());

        // Fraction of budget consumed so far.
        features.put("progress", state.budgetProgress());

        // Objective normalised by the running observed range.
        // Uses running extrema only; see class-level normalisation note.
        final double range = Math.max(state.runningMax() - state.runningMin(), RANGE_FLOOR);
        final double objNorm = (state.currentObjective() - state.runningMin()) / range;
        features.put("obj_norm", objNorm);

        // Gap from current incumbent to best-so-far, scaled by running range.
        final double gapToBest = (state.currentObjective() - state.bestSoFar()) / range;
        features.put("gap_to_best", gapToBest);

        // Iterations since best-so-far was last improved.
        features.put("iters_since_improve", (double) state.iterationsSinceImprovement());

        // Fraction of the last 50 applications that improved their target.
        // A delta < 0 means improvement for minimisation.
        final List<Double> deltas = state.recentDeltas();
        final double improveRate;
        if (deltas.isEmpty()) {
            improveRate = 0.0;
        } else {
            long improved = 0;
            for (final double d : deltas) {
                if (d < 0.0) {
                    improved++;
                }
            }
            improveRate = (double) improved / deltas.size();
        }
        features.put("improve_rate_50", improveRate);

        // Mean log return over the last 50 applications, ignoring undefined (NaN) entries.
        final List<Double> logReturns = state.recentLogReturns();
        final double meanLogRet;
        if (logReturns.isEmpty()) {
            meanLogRet = 0.0;
        } else {
            double sum = 0.0;
            int count  = 0;
            for (final double lr : logReturns) {
                if (!Double.isNaN(lr)) {
                    sum += lr;
                    count++;
                }
            }
            meanLogRet = (count > 0) ? sum / count : 0.0;
        }
        features.put("mean_logret_50", meanLogRet);

        // Previous three heuristic indices (categorical, sentinel -1 for absence).
        final List<Integer> history = state.lastHeuristics();
        for (int i = 0; i < SearchState.HISTORY_LENGTH; i++) {
            final int idx = (i < history.size()) ? history.get(i) : -1;
            features.put("last_h" + (i + 1), (double) idx);
        }

        // Previous three heuristic class ordinals (categorical, sentinel -1 for absence).
        final List<Integer> classes = state.lastHeuristicClasses();
        for (int i = 0; i < SearchState.HISTORY_LENGTH; i++) {
            final int cls = (i < classes.size()) ? classes.get(i) : -1;
            features.put("last_class" + (i + 1), (double) cls);
        }

        // Iterations since the last accepted move.
        features.put("iters_since_accept", (double) state.iterationsSinceAccept());

        // Population diversity (NaN for single-point search).
        features.put("pop_diversity", state.populationDiversity());

        // Rank of the target individual within the population (-1 for single-point).
        features.put("pop_target_rank", (double) state.populationTargetRank());

        return features;
    }
}
