package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import za.ac.up.cos790.acceptance.AILTA;
import za.ac.up.cos790.acceptance.ImprovingOrEqual;
import za.ac.up.cos790.acceptance.LateAcceptance;
import za.ac.up.cos790.acceptance.NaiveAcceptance;
import za.ac.up.cos790.acceptance.SimulatedAnnealing;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Tests for each concrete {@code AcceptanceStrategy} implementation.
 */
class AcceptanceStrategyTest {

    @Test
    void naiveAcceptanceAlwaysAccepts() {
        final NaiveAcceptance strategy = new NaiveAcceptance();
        assertTrue(strategy.accept(100.0, 200.0, 100.0, 0L),
                "NaiveAcceptance should accept worsening candidates.");
        assertTrue(strategy.accept(100.0, 100.0, 100.0, 0L),
                "NaiveAcceptance should accept equal candidates.");
        assertTrue(strategy.accept(100.0, 50.0, 50.0, 0L),
                "NaiveAcceptance should accept improving candidates.");
    }

    @Test
    void improvingOrEqualAcceptsNonWorsening() {
        final ImprovingOrEqual strategy = new ImprovingOrEqual();
        assertTrue(strategy.accept(100.0, 99.0, 99.0, 0L),
                "ImprovingOrEqual should accept an improving candidate.");
        assertTrue(strategy.accept(100.0, 100.0, 100.0, 0L),
                "ImprovingOrEqual should accept an equal candidate.");
        assertFalse(strategy.accept(100.0, 101.0, 100.0, 0L),
                "ImprovingOrEqual should reject a worsening candidate.");
    }

    /**
     * Verifies the published Late Acceptance rule (Q17-Q19):
     * accept if candidate is no worse than the incumbent OR no worse than the
     * objective L steps ago; update history only when the new incumbent is better.
     *
     * <p>History trace (L=3, slots indexed 0-2, head advances each step):
     * <pre>
     *   Step 0: h=[MAX,MAX,MAX], head=0. inc=100, cand=90 (improving -> accept).
     *           newInc=90, 90 < MAX -> h[0]=90. head=1. h=[90,MAX,MAX].
     *   Step 1: h=[90,MAX,MAX], head=1. inc=90, cand=85 (improving -> accept).
     *           newInc=85, 85 < MAX -> h[1]=85. head=2. h=[90,85,MAX].
     *   Step 2: h=[90,85,MAX], head=2. inc=85, cand=92. 92<=85? No. 92<=MAX? Yes -> accept.
     *           newInc=92, 92 < MAX -> h[2]=92. head=0. h=[90,85,92].
     *   Step 3: h=[90,85,92], head=0. inc=92, cand=98. 98<=92? No. 98<=90? No -> REJECT.
     *           newInc=92, 92 < 90? No -> h[0] unchanged. head=1. h=[90,85,92].
     *   Step 4: h=[90,85,92], head=1. inc=92, cand=84. 84<=92? Yes -> accept.
     * </pre>
     */
    @Test
    void lateAcceptanceAcceptsWhenCandidateBeatsPastValue() {
        final LateAcceptance la = new LateAcceptance(3);

        // Step 0: improving move always accepted.
        assertTrue(la.accept(100.0, 90.0, 50.0, 0L),
                "Step 0: improving candidate 90 should be accepted.");

        // Step 1: improving move.
        assertTrue(la.accept(90.0, 85.0, 50.0, 1L),
                "Step 1: improving candidate 85 should be accepted.");

        // Step 2: worsening but history slot holds MAX_VALUE -> accepted.
        assertTrue(la.accept(85.0, 92.0, 50.0, 2L),
                "Step 2: candidate 92 vs MAX_VALUE history should be accepted.");

        // Step 3: 98 > incumbent 92 AND 98 > history[0]=90 -> rejected.
        assertFalse(la.accept(92.0, 98.0, 50.0, 3L),
                "Step 3: candidate 98 worse than both incumbent 92 and history[0]=90 should be rejected.");

        // Step 4: candidate 84 <= incumbent 92 -> accepted (improving).
        assertTrue(la.accept(92.0, 84.0, 50.0, 4L),
                "Step 4: improving candidate 84 should be accepted.");
    }

    /**
     * Verifies that changing bestSoFar cannot change a Late Acceptance decision (Q19).
     */
    @Test
    void lateAcceptanceBestSoFarArgIsUnused() {
        final LateAcceptance la = new LateAcceptance(5);
        // Warm up history with a real value.
        la.accept(100.0, 100.0, 100.0, 0L);

        final boolean withLowBest  = la.accept(100.0, 105.0, 10.0, 1L);
        final LateAcceptance la2   = new LateAcceptance(5);
        la2.accept(100.0, 100.0, 100.0, 0L);
        final boolean withHighBest = la2.accept(100.0, 105.0, 999.0, 1L);

        assertTrue(withLowBest == withHighBest,
                "Changing bestSoFar must not change the Late Acceptance decision.");
    }

    /**
     * Verifies that SimulatedAnnealing accepts all improving moves.
     */
    @Test
    void simulatedAnnealingAcceptsImprovingMoves() {
        final SimulatedAnnealing sa = new SimulatedAnnealing(1000.0, 0.99, 42L);
        assertTrue(sa.accept(100.0, 99.0, 90.0, 0L),
                "SA should always accept an improving move.");
        assertTrue(sa.accept(100.0, 100.0, 90.0, 1L),
                "SA should accept an equal move.");
    }

    /**
     * Verifies that AILTA accepts improving moves unconditionally and rejects
     * moves that worsen by more than the current threshold.
     */
    @Test
    void ailtaAcceptsImprovingAndRejectsLargeWorsening() {
        // Starting objective 1000, total budget 100 iterations.
        // Initial threshold = 2% of 1000 = 20.
        final AILTA ailta = new AILTA(1000.0, 100L);

        // At iteration 0 (start), threshold = 20. Delta = +5 <= 20 -> accept.
        assertTrue(ailta.accept(100.0, 105.0, 90.0, 0L),
                "AILTA should accept worsening within threshold.");

        // Delta = +25 > 20 -> reject.
        assertFalse(ailta.accept(100.0, 125.0, 90.0, 0L),
                "AILTA should reject worsening exceeding threshold.");

        // Improving move always accepted.
        assertTrue(ailta.accept(100.0, 80.0, 80.0, 0L),
                "AILTA should always accept an improving move.");

        // At iteration 50 (half budget), threshold = 10.
        // Delta = +15 > 10 -> reject.
        assertFalse(ailta.accept(100.0, 115.0, 90.0, 50L),
                "AILTA threshold decays: worsening 15 should be rejected at mid-run.");

        // At iteration 100 (end of budget), threshold = 0: only non-worsening accepted.
        assertFalse(ailta.accept(100.0, 100.1, 90.0, 100L),
                "AILTA threshold is zero at budget exhaustion; worsening should be rejected.");
        assertTrue(ailta.accept(100.0, 100.0, 90.0, 100L),
                "AILTA accepts equal moves even at zero threshold.");
    }
}
