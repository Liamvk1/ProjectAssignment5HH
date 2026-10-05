package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import za.ac.up.cos790.experiment.BudgetPolicy;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link BudgetPolicy}, including the per-member budget scaling
 * introduced by Item 6.
 */
class BudgetPolicyTest {

    // -------------------------------------------------------------------------
    // Existing behaviour
    // -------------------------------------------------------------------------

    @Test
    void iterationBasedExhaustsAtLimit() {
        final BudgetPolicy p = BudgetPolicy.iterationBased(100L);
        assertFalse(p.isExhausted(99L, 0L), "Should not be exhausted before the limit.");
        assertTrue(p.isExhausted(100L, 0L), "Should be exhausted at the limit.");
    }

    @Test
    void timeBasedExhaustsAtLimit() {
        final BudgetPolicy p = BudgetPolicy.timeBased(5000L);
        assertFalse(p.isExhausted(0L, 4999L));
        assertTrue(p.isExhausted(0L, 5000L));
    }

    @Test
    void iterationBasedProgressIsLinear() {
        final BudgetPolicy p = BudgetPolicy.iterationBased(100L);
        assertEquals(0.5, p.progress(50L, 0L), 1e-9);
        assertEquals(1.0, p.progress(100L, 0L), 1e-9);
    }

    // -------------------------------------------------------------------------
    // budgetScaling = "none" (DD-04 default)
    // -------------------------------------------------------------------------

    @Test
    void fromConfigScalingNoneMatchesFlatIterationBased() {
        final BudgetPolicy none = BudgetPolicy.fromConfig("iterations", 1000L, "none", 10);
        final BudgetPolicy flat = BudgetPolicy.iterationBased(1000L);

        assertEquals(flat.isExhausted(999L, 0L), none.isExhausted(999L, 0L));
        assertEquals(flat.isExhausted(1000L, 0L), none.isExhausted(1000L, 0L));
    }

    @Test
    void fromConfigNullScalingDefaultsToNone() {
        // null budgetScaling must behave identically to "none".
        final BudgetPolicy p = BudgetPolicy.fromConfig("iterations", 100L, null, 5);
        assertFalse(p.isExhausted(99L, 0L));
        assertTrue(p.isExhausted(100L, 0L));
    }

    // -------------------------------------------------------------------------
    // budgetScaling = "per_member" (Item 6)
    // -------------------------------------------------------------------------

    @Test
    void fromConfigPerMemberScalesByPopulationSize() {
        final int popSize = 5;
        final long baseLimit = 100L;
        final BudgetPolicy p = BudgetPolicy.fromConfig("iterations", baseLimit, "per_member", popSize);

        // Effective limit = baseLimit * popSize = 500.
        assertFalse(p.isExhausted(499L, 0L));
        assertTrue(p.isExhausted(500L, 0L));
    }

    @Test
    void fromConfigPerMemberProgressIsRelativeToScaledLimit() {
        final BudgetPolicy p = BudgetPolicy.fromConfig("iterations", 100L, "per_member", 4);
        // Effective limit = 400.
        assertEquals(0.25, p.progress(100L, 0L), 1e-9);
        assertEquals(1.0,  p.progress(400L, 0L), 1e-9);
    }

    @Test
    void fromConfigTimeBudgetIgnoresScaling() {
        // Time-based budgets must not be scaled (wall-clock is already shared).
        final BudgetPolicy p = BudgetPolicy.fromConfig("time", 5000L, "per_member", 10);
        assertFalse(p.isExhausted(0L, 4999L));
        assertTrue(p.isExhausted(0L, 5000L));
    }

    // -------------------------------------------------------------------------
    // Error handling
    // -------------------------------------------------------------------------

    @Test
    void fromConfigUnknownScalingThrows() {
        assertThrows(IllegalArgumentException.class,
                () -> BudgetPolicy.fromConfig("iterations", 100L, "quadratic", 5));
    }

    @Test
    void fromConfigUnknownBudgetTypeThrows() {
        assertThrows(IllegalArgumentException.class,
                () -> BudgetPolicy.fromConfig("wall_clock", 100L));
    }
}
