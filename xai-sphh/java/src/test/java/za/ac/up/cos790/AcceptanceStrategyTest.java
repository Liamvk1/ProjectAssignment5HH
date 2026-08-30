package za.ac.up.cos790;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import za.ac.up.cos790.acceptance.ImprovingOrEqual;
import za.ac.up.cos790.acceptance.LateAcceptance;
import za.ac.up.cos790.acceptance.NaiveAcceptance;
import za.ac.up.cos790.acceptance.SimulatedAnnealing;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Stub tests for each concrete {@code AcceptanceStrategy} implementation.
 *
 * <p>Each test method is a placeholder. It will be filled in once the corresponding
 * implementation is written. Until then, tests for unimplemented strategies are
 * marked {@link Disabled} so that the test suite passes without false positives.
 */
class AcceptanceStrategyTest {

    /**
     * Verifies that {@link NaiveAcceptance} accepts every candidate unconditionally.
     */
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

    /**
     * Verifies that {@link ImprovingOrEqual} accepts only non-worsening candidates.
     */
    @Test
    void improvingOrEqualAcceptsNonWorsening() {
        final ImprovingOrEqual strategy = new ImprovingOrEqual();
        assertTrue(strategy.accept(100.0, 99.0, 99.0, 0L),
                "ImprovingOrEqual should accept an improving candidate.");
        assertTrue(strategy.accept(100.0, 100.0, 100.0, 0L),
                "ImprovingOrEqual should accept an equal candidate.");
        assertTrue(!strategy.accept(100.0, 101.0, 100.0, 0L),
                "ImprovingOrEqual should reject a worsening candidate.");
    }

    /**
     * Stub test for {@link LateAcceptance}.
     * Disabled until the strategy is implemented (see design decision DD-02).
     */
    @Test
    @Disabled("TODO (DD-02): LateAcceptance is not yet implemented.")
    void lateAcceptanceAcceptsWhenCandidateBeatsPastValue() {
        // TODO (DD-02): Construct a LateAcceptance strategy, run it through a known
        //               sequence of objectives, and assert the expected accept/reject
        //               decisions at each step.
    }

    /**
     * Stub test for {@link SimulatedAnnealing}.
     * Disabled until the strategy is implemented (see design decision DD-02).
     */
    @Test
    @Disabled("TODO (DD-02): SimulatedAnnealing is not yet implemented.")
    void simulatedAnnealingProbabilityDeclinesToZeroAtLowTemperature() {
        // TODO (DD-02): At a very low temperature the SA strategy should behave like
        //               ImprovingOrEqual. Verify this property.
    }
}
