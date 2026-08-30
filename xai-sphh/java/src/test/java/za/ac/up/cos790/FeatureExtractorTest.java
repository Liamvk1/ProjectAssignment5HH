package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import za.ac.up.cos790.state.FeatureExtractor;
import za.ac.up.cos790.state.SearchState;

import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Tests for {@link FeatureExtractor}, covering the Decision 28 feature specification.
 */
class FeatureExtractorTest {

    /** Builds a minimal single-point state. */
    private static SearchState minimalState(final int heuristicCount) {
        return SearchState.singlePoint(
                heuristicCount, 0L, 0.0,
                100.0, 100.0, 0L, 0L,
                100.0, 100.0,
                Collections.emptyList(), Collections.emptyList(),
                Collections.emptyList(), Collections.emptyList()
        );
    }

    /**
     * The feature map must contain every name listed in FEATURE_NAMES, in order.
     */
    @Test
    void extractedMapKeysMatchFeatureNames() {
        final Map<String, Double> features = FeatureExtractor.extract(minimalState(5));
        final List<String> expectedKeys    = FeatureExtractor.FEATURE_NAMES;

        assertEquals(expectedKeys, List.copyOf(features.keySet()),
                "Feature map keys must match FEATURE_NAMES in order.");
    }

    /**
     * Sentinel value for missing heuristic history is -1, not 0.
     * Using 0 would be ambiguous with heuristic index 0.
     */
    @Test
    void sentinelForMissingHeuristicHistoryIsNegativeOne() {
        final Map<String, Double> features = FeatureExtractor.extract(minimalState(5));
        assertEquals(-1.0, features.get("last_h1"), 1e-12,
                "feat_last_h1 should be -1 when no heuristic has been applied yet.");
        assertEquals(-1.0, features.get("last_h2"), 1e-12,
                "feat_last_h2 should be -1 when fewer than 2 heuristics have been applied.");
        assertEquals(-1.0, features.get("last_h3"), 1e-12,
                "feat_last_h3 should be -1 when fewer than 3 heuristics have been applied.");
        assertEquals(-1.0, features.get("last_class1"), 1e-12,
                "feat_last_class1 should be -1 when no heuristic class is recorded.");
    }

    /**
     * Objective normalisation must use running extrema only (not full-run range).
     * Modifying state values from after time t must not affect features computed at t.
     */
    @Test
    void objNormUsesRunningExtremaNotFutureValues() {
        // At step t: runningMin=50, runningMax=150, current=100 -> norm = (100-50)/(150-50) = 0.5
        final SearchState stateAtT = SearchState.singlePoint(
                4, 5L, 0.5, 100.0, 50.0, 3L, 1L,
                50.0, 150.0,
                Collections.emptyList(), Collections.emptyList(),
                Collections.emptyList(), Collections.emptyList()
        );
        final Map<String, Double> features = FeatureExtractor.extract(stateAtT);
        assertEquals(0.5, features.get("obj_norm"), 1e-10,
                "obj_norm should be (100-50)/(150-50) = 0.5 with running extrema.");

        // Simulating a future step with wider range must NOT change the t-features.
        // (This is enforced by the immutable SearchState record.)
        final SearchState stateAtTPlus1 = SearchState.singlePoint(
                4, 6L, 0.6, 200.0, 50.0, 4L, 2L,
                50.0, 200.0,   // wider running range after the step
                Collections.emptyList(), Collections.emptyList(),
                Collections.emptyList(), Collections.emptyList()
        );
        final Map<String, Double> futureFeatures = FeatureExtractor.extract(stateAtTPlus1);
        assertFalse(features.get("obj_norm").equals(futureFeatures.get("obj_norm")),
                "Features computed at different steps must be independent (no leakage).");
    }

    /**
     * feat_improve_rate_50 should reflect the fraction of the delta window with negative values.
     */
    @Test
    void improveRate50ReflectsWindowFraction() {
        // 3 out of 5 deltas are negative (improvements).
        final List<Double> deltas = List.of(-1.0, 2.0, -3.0, 4.0, -5.0);
        final SearchState state = SearchState.singlePoint(
                4, 5L, 0.5, 100.0, 90.0, 1L, 0L,
                90.0, 100.0,
                deltas, Collections.emptyList(),
                Collections.emptyList(), Collections.emptyList()
        );
        final Map<String, Double> features = FeatureExtractor.extract(state);
        assertEquals(3.0 / 5.0, features.get("improve_rate_50"), 1e-10,
                "improve_rate_50 should be 3/5 when 3 of 5 deltas are negative.");
    }

    /**
     * feat_mean_logret_50 should average only non-NaN log return values.
     */
    @Test
    void meanLogret50IgnoresNaN() {
        final List<Double> logReturns = List.of(-0.1, Double.NaN, -0.3, Double.NaN, -0.5);
        final SearchState state = SearchState.singlePoint(
                4, 5L, 0.5, 100.0, 90.0, 1L, 0L,
                90.0, 100.0,
                Collections.emptyList(), logReturns,
                Collections.emptyList(), Collections.emptyList()
        );
        final Map<String, Double> features = FeatureExtractor.extract(state);
        final double expected = (-0.1 + -0.3 + -0.5) / 3.0;
        assertEquals(expected, features.get("mean_logret_50"), 1e-10,
                "mean_logret_50 must skip NaN entries.");
    }

    /**
     * gap_to_best should be zero when the incumbent equals the best.
     */
    @Test
    void gapToBestIsZeroWhenAtBest() {
        final SearchState state = SearchState.singlePoint(
                4, 0L, 0.0, 80.0, 80.0, 0L, 0L,
                80.0, 120.0,
                Collections.emptyList(), Collections.emptyList(),
                Collections.emptyList(), Collections.emptyList()
        );
        final Map<String, Double> features = FeatureExtractor.extract(state);
        assertEquals(0.0, features.get("gap_to_best"), 1e-10,
                "gap_to_best should be zero when current equals best_so_far.");
    }

    /**
     * Population features (pop_diversity, pop_target_rank) are NaN/-1 for single-point.
     */
    @Test
    void singlePointPopulationFeaturesHaveSentinelValues() {
        final Map<String, Double> features = FeatureExtractor.extract(minimalState(3));
        assertTrue(Double.isNaN(features.get("pop_diversity")),
                "pop_diversity should be NaN for single-point search.");
        assertEquals(-1.0, features.get("pop_target_rank"), 1e-12,
                "pop_target_rank should be -1 for single-point search.");
    }

    /**
     * The extracted map must have exactly as many entries as FEATURE_NAMES.
     */
    @Test
    void extractedMapSizeMatchesFeatureNameCount() {
        final Map<String, Double> features = FeatureExtractor.extract(minimalState(6));
        assertEquals(FeatureExtractor.FEATURE_NAMES.size(), features.size(),
                "Extracted map must have exactly FEATURE_NAMES.size() entries.");
    }

    /**
     * All feature values must be finite or NaN; none may be Infinite.
     */
    @Test
    void noFeatureValueIsInfinite() {
        final Map<String, Double> features = FeatureExtractor.extract(minimalState(4));
        for (final Map.Entry<String, Double> entry : features.entrySet()) {
            assertFalse(Double.isInfinite(entry.getValue()),
                    "Feature '" + entry.getKey() + "' must not be Infinite.");
        }
    }
}
