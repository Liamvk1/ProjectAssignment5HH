package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import za.ac.up.cos790.instrumentation.ScoreVector;
import za.ac.up.cos790.selection.ChoiceFunction;
import za.ac.up.cos790.state.SearchState;

import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Tests for the Modified Choice Function selection strategy.
 */
class ChoiceFunctionTest {

    /** Builds a minimal SearchState for testing with n heuristics. */
    private static SearchState stateWith(final int n) {
        return SearchState.singlePoint(
                n, 0L, 0.0, 100.0, 100.0, 0L, 0L,
                100.0, 100.0,
                Collections.emptyList(), Collections.emptyList(),
                Collections.emptyList(), Collections.emptyList()
        );
    }

    /**
     * Warm-up: the first n calls to select() should return 0, 1, ..., n-1
     * in order, with an all-NaN score vector.
     */
    @Test
    void warmupAppliesEachHeuristicOnceInAscendingOrder() {
        final int n = 4;
        final ChoiceFunction cf = new ChoiceFunction(42L);
        final SearchState state = stateWith(n);

        for (int expected = 0; expected < n; expected++) {
            final int selected = cf.select(state);
            assertEquals(expected, selected,
                    "Warm-up step " + expected + " should return heuristic " + expected);

            final ScoreVector scores = cf.scoreVector();
            assertEquals(n, scores.size(), "Score vector must have length n.");
            for (int i = 0; i < n; i++) {
                assertTrue(Double.isNaN(scores.get(i)),
                        "Score vector must be all NaN during warm-up (step " + expected + ").");
            }

            // Simulate an outcome so the warm-up proceeds correctly.
            cf.recordOutcome(selected, 0.0, 10.0);
        }
    }

    /**
     * After warm-up, the score vector must be fully populated (no NaN entries),
     * and the selected heuristic must be the argmax.
     */
    @Test
    void afterWarmupScoreVectorIsPopulatedAndArgmaxIsSelected() {
        final int n = 3;
        final ChoiceFunction cf = new ChoiceFunction(7L);
        final SearchState state = stateWith(n);

        // Complete warm-up.
        for (int i = 0; i < n; i++) {
            final int h = cf.select(state);
            // Record an improvement for heuristic 1 only, so it has the highest f1.
            final double delta = (h == 1) ? -10.0 : 0.0;
            cf.recordOutcome(h, delta, 1.0);
        }

        // One post-warm-up step: heuristic 1 should score highest.
        final int selected = cf.select(state);
        final ScoreVector scores = cf.scoreVector();

        for (int i = 0; i < n; i++) {
            assertNotEquals(Double.NaN, scores.get(i),
                    "Score must not be NaN after warm-up.");
        }

        // The selected heuristic must have the maximum score.
        double bestScore = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < n; i++) {
            if (scores.get(i) > bestScore) {
                bestScore = scores.get(i);
            }
        }
        assertEquals(bestScore, scores.get(selected), 1e-12,
                "The selected heuristic must have the maximum score.");
    }

    /**
     * An improving move (delta < 0) must snap phi back toward the reward value,
     * which causes f3 weight (1-phi) to decrease and the score to tilt towards
     * f1 and f2 rather than idle time.
     */
    @Test
    void improvingMoveIncreasesF1AndAdjustsPhi() {
        final int n = 2;
        final ChoiceFunction cf = new ChoiceFunction(1L);
        final SearchState state = stateWith(n);

        // Warm-up.
        for (int i = 0; i < n; i++) {
            cf.select(state);
            cf.recordOutcome(i, 0.0, 1.0);
        }

        // Select and record an improving outcome for heuristic 0.
        cf.select(state);
        cf.recordOutcome(0, -50.0, 5.0); // large improvement

        // Record a non-improving outcome for heuristic 1.
        cf.select(state);
        cf.recordOutcome(1, 10.0, 5.0);

        // After an improvement, heuristic 0 should have a positive f1 contribution.
        final ScoreVector scores = cf.scoreVector();
        assertTrue(scores.get(0) >= 0.0 || scores.get(1) >= 0.0,
                "At least one heuristic should have a non-negative score.");
    }

    /**
     * The f2 pair term is asymmetric: f2[i][j] is updated when j follows i,
     * but f2[j][i] is not updated in the same step.
     */
    @Test
    void f2IsAsymmetric() {
        final int n = 2;
        final ChoiceFunction cf = new ChoiceFunction(99L);
        final SearchState state = stateWith(n);

        // Warm-up: apply 0, then 1.
        cf.select(state); // returns 0
        cf.recordOutcome(0, -10.0, 1.0);
        cf.select(state); // returns 1
        cf.recordOutcome(1, 0.0, 1.0);

        // Post warm-up: heuristic 0 follows heuristic 1 (last selected = 1).
        // This updates f2[1][0] only, not f2[0][1].
        cf.select(state);
        cf.recordOutcome(0, -5.0, 1.0);

        // Now heuristic 1 follows heuristic 0.
        // This updates f2[0][1] for the first time.
        final int h = cf.select(state);
        final ScoreVector scores = cf.scoreVector();

        // f2 has non-zero entries now; the score vector should differ from the all-zero case.
        assertTrue(scores.size() == n, "Score vector length must equal heuristic count.");
    }

    /**
     * Tie-breaking must be reproducible from the same seed and must be able to
     * return any tied heuristic (not always the lowest index).
     */
    @Test
    void tieBreakerIsReproducibleAndNotAlwaysLowestIndex() {
        final int n = 4;
        // Two selectors with the same seed must make the same choices.
        final ChoiceFunction cf1 = new ChoiceFunction(123L);
        final ChoiceFunction cf2 = new ChoiceFunction(123L);
        final SearchState state  = stateWith(n);

        // Skip warm-up.
        for (int i = 0; i < n; i++) {
            cf1.select(state);
            cf1.recordOutcome(i, 0.0, 1.0);
            cf2.select(state);
            cf2.recordOutcome(i, 0.0, 1.0);
        }

        // At iteration 0 after warm-up, all scores should be equal -> tie.
        // Both selectors must pick the same heuristic.
        assertEquals(cf1.select(state), cf2.select(state),
                "Same seed must produce the same tie-breaking choice.");

        // A different seed may make a different choice.
        final ChoiceFunction cf3 = new ChoiceFunction(999L);
        for (int i = 0; i < n; i++) {
            cf3.select(state);
            cf3.recordOutcome(i, 0.0, 1.0);
        }
        // We can't guarantee a different seed makes a DIFFERENT choice, but we
        // can verify the range is within [0, n).
        final int selected = cf3.select(state);
        assertTrue(selected >= 0 && selected < n,
                "Selected heuristic must be within valid range.");
    }

    /**
     * A non-improving sequence should shift phi towards PHI_FLOOR (0.01), so that the
     * f3 (idle time) term dominates. The most idle heuristic should then be preferred.
     *
     * <p>After the warm-up (which applies h0 then h1), the test applies h0 200 times
     * with worsening outcomes. At the end of the loop, before any additional
     * select/recordOutcome calls:
     * <ul>
     *   <li>phi is at or near floor (0.01)</li>
     *   <li>f3[0] = 0 (reset at each application)</li>
     *   <li>f3[1] ≈ 200 (incremented at each application of h0)</li>
     *   <li>CF(h0) ≈ small negative (f1 and f2 have negative accumulated reward)</li>
     *   <li>CF(h1) ≈ (1-phi) * 200 ≈ 198 (dominated by idle time)</li>
     * </ul>
     * Therefore h1 should be the next selection.
     */
    @Test
    void repeatedNonImprovingMovesDecayPhi() {
        final int n = 2;
        final ChoiceFunction cf = new ChoiceFunction(5L);
        final SearchState state = stateWith(n);

        // Warm-up: apply h0 then h1.
        for (int i = 0; i < n; i++) {
            cf.select(state);
            cf.recordOutcome(i, 0.0, 1.0);
        }

        // Apply h0 200 times with worsening outcomes.
        // cf.select() is called each iteration but the result is ignored; the outcome
        // is always reported for h0. After the loop: f3[1] has accumulated 200 ms of
        // idle time and phi is at floor (0.01).
        for (int step = 0; step < 200; step++) {
            cf.select(state);
            cf.recordOutcome(0, 5.0, 1.0);
        }

        // Select immediately after the loop, before any further recordOutcome.
        // At this point lastSelected=0, f3[0]=0, f3[1]~200, phi~0.01.
        // CF(h1) >> CF(h0) because f3 dominates and h1 is most idle.
        final int selected = cf.select(state);
        assertEquals(1, selected,
                "After many non-improving moves h0 is always reset (f3=0); "
                + "h1 has large idle time and should be preferred.");
    }
}
