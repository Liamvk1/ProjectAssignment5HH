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
        // TODO (DD-01): Instantiate the correct HyFlex domain classes once the jars are
        //               in place. The lambda bodies below are placeholders that reference
        //               the expected class names from the CHeSC distribution.
        //               e.g. () -> new SAT(seed), () -> new BinPacking(seed), etc.
        //               Instance index ranges follow the CHeSC 2011 specification.
        return Map.of(
                "SAT",                  new DomainEntry(
                        () -> { throw new UnsupportedOperationException("TODO: instantiate SAT domain"); },
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "BinPacking",           new DomainEntry(
                        () -> { throw new UnsupportedOperationException("TODO: instantiate BinPacking domain"); },
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "PersonnelScheduling",  new DomainEntry(
                        () -> { throw new UnsupportedOperationException("TODO: instantiate PersonnelScheduling domain"); },
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "FlowShop",             new DomainEntry(
                        () -> { throw new UnsupportedOperationException("TODO: instantiate FlowShop domain"); },
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "TSP",                  new DomainEntry(
                        () -> { throw new UnsupportedOperationException("TODO: instantiate TSP domain"); },
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)),

                "VRP",                  new DomainEntry(
                        () -> { throw new UnsupportedOperationException("TODO: instantiate VRP domain"); },
                        List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9))
        );
    }
}
