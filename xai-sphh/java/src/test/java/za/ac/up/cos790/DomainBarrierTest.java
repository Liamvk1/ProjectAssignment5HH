package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import za.ac.up.cos790.state.FeatureExtractor;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Asserts that the published feature name list does not contain domain-specific terms.
 *
 * <p>This test guards against accidental domain-barrier violations in
 * {@link FeatureExtractor#FEATURE_NAMES}. Adding a feature whose name contains a
 * term from the deny list will cause this test to fail, requiring deliberate review.
 *
 * <p>The deny list is intentionally conservative. It covers terminology specific to
 * the six HyFlex domains: SAT (Boolean satisfiability), Bin Packing, Personnel
 * Scheduling, Flow Shop, TSP (Travelling Salesman), and VRP (Vehicle Routing).
 */
class DomainBarrierTest {

    /**
     * Substrings that must not appear in any feature name.
     * Case-insensitive matching is applied.
     */
    private static final List<String> DENY_LIST = List.of(
            // SAT domain
            "clause", "literal", "variable", "sat", "boolean", "cnf",
            // Bin Packing domain
            "bin", "item", "weight", "capacity",
            // Personnel Scheduling domain
            "shift", "nurse", "employee", "roster", "schedule",
            // Flow Shop domain
            "job", "machine", "makespan", "flowshop", "flow_shop",
            // TSP domain
            "city", "tour", "distance", "tsp", "salesman",
            // VRP domain
            "vehicle", "route", "depot", "demand", "vrp",
            // Generic problem-structure terms
            "node", "edge", "graph", "vertex", "arc",
            "constraint", "penalty", "violation"
    );

    /**
     * Asserts that every name in {@link FeatureExtractor#FEATURE_NAMES} is free of
     * domain-specific terminology.
     */
    @Test
    void featureNamesMustNotContainDomainSpecificTerms() {
        final List<String> names = FeatureExtractor.FEATURE_NAMES;

        for (final String name : names) {
            final String lower = name.toLowerCase();
            for (final String forbidden : DENY_LIST) {
                assertTrue(
                        !lower.contains(forbidden.toLowerCase()),
                        "Feature name '" + name + "' contains forbidden term '" + forbidden
                                + "'. This may be a domain-barrier violation. "
                                + "If the term is genuinely domain-agnostic, remove it from the deny list "
                                + "with a comment explaining why."
                );
            }
        }
    }
}
