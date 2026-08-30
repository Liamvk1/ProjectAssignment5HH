package za.ac.up.cos790.domain;

import AbstractClasses.ProblemDomain;

import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

/**
 * Maps domain name strings to HyFlex {@link ProblemDomain} constructors and records
 * the valid instance indices for each domain.
 *
 * <p>Domain names used here must match the {@code domain} field of
 * {@code config/experiments/*.yaml} exactly.
 *
 * <p>HyFlex ships with six domains. Instance index ranges are taken from the CHeSC 2011
 * competition specification. Extend this registry if additional domains are added.
 */
public final class DomainRegistry {

    /**
     * Metadata for a registered domain.
     *
     * @param factory        supplier that constructs a fresh {@link ProblemDomain} instance
     * @param instanceIndices valid instance index values for this domain
     */
    public record DomainEntry(
            Supplier<ProblemDomain> factory,
            List<Integer> instanceIndices
    ) {}

    private static final Map<String, DomainEntry> REGISTRY = buildRegistry();

    /** Utility class; no instances required. */
    private DomainRegistry() {}

    /**
     * Returns the domain entry for the given domain name.
     *
     * @param domainName the domain name as used in experiment YAML files
     * @return the corresponding {@link DomainEntry}
     * @throws IllegalArgumentException if the domain name is not registered
     */
    public static DomainEntry get(final String domainName) {
        final DomainEntry entry = REGISTRY.get(domainName);
        if (entry == null) {
            throw new IllegalArgumentException(
                    "Unknown domain: '" + domainName + "'. Registered domains: " + REGISTRY.keySet());
        }
        return entry;
    }

    /**
     * Returns an unmodifiable view of all registered domain names.
     *
     * @return set of valid domain name strings
     */
    public static java.util.Set<String> registeredNames() {
        return REGISTRY.keySet();
    }

    private static Map<String, DomainEntry> buildRegistry() {
        // Domain constructors from the CHeSC 2011 distribution.
        // All domains take a single long seed. Instance index ranges follow the
        // CHeSC 2011 specification (10 instances per domain, indices 0-9).
        // PersonnelScheduling is in a separate jar (chesc-ps.jar); all others
        // are in chesc-fixed-no-ps.jar.
        return Map.of(
                "SAT", new DomainEntry(
                        () -> new SAT.SAT(System.nanoTime()),
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "BinPacking", new DomainEntry(
                        () -> new BinPacking.BinPacking(System.nanoTime()),
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "FlowShop", new DomainEntry(
                        () -> new FlowShop.FlowShop(System.nanoTime()),
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "TSP", new DomainEntry(
                        () -> new travelingSalesmanProblem.TSP(System.nanoTime()),
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "VRP", new DomainEntry(
                        () -> new VRP.VRP(System.nanoTime()),
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "PersonnelScheduling", new DomainEntry(
                        () -> new PersonnelScheduling.PersonnelScheduling(System.nanoTime()),
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9))
        );
    }
}
