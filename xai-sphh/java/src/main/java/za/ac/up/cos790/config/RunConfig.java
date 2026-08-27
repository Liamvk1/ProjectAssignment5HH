package za.ac.up.cos790.config;

import java.nio.file.Path;
import java.util.Map;

/**
 * Immutable configuration record for a single hyper-heuristic run.
 *
 * <p>All fields are set from the YAML experiment file loaded by {@link ConfigLoader}.
 * Using a Java record guarantees immutability without boilerplate.
 *
 * @param techniqueName      Identifier for the hyper-heuristic technique to use.
 *                           Must match a key registered in {@code ExperimentRunner}.
 * @param domain             HyFlex domain name. Must match a key in {@code DomainRegistry}.
 * @param instanceIndex      Zero-based index of the problem instance within the domain.
 * @param seed               Random seed for reproducibility.
 * @param budgetType         Either {@code "time"} (milliseconds) or {@code "iterations"}.
 * @param budgetValue        Budget limit in the units given by {@code budgetType}.
 * @param outputDirectory    Directory into which trace CSV and run manifest are written.
 * @param techniqueParameters Technique-specific key/value pairs passed to the strategy.
 */
public record RunConfig(
        String techniqueName,
        String domain,
        int instanceIndex,
        long seed,
        String budgetType,
        long budgetValue,
        Path outputDirectory,
        Map<String, String> techniqueParameters
) {

    /**
     * Compact constructor that defensively copies the parameter map to ensure immutability.
     */
    public RunConfig {
        techniqueParameters = Map.copyOf(techniqueParameters);
    }
}
