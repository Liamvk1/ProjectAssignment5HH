package za.ac.up.cos790.experiment;

import za.ac.up.cos790.config.RunConfig;

import java.io.IOException;
import java.nio.file.Files;

/**
 * Orchestrates the execution of a single hyper-heuristic run as described by a
 * {@link RunConfig}.
 *
 * <p>Responsibilities:
 * <ul>
 *   <li>Look up the requested domain and technique.</li>
 *   <li>Instantiate the problem domain with the configured instance.</li>
 *   <li>Instantiate the hyper-heuristic and its strategy objects.</li>
 *   <li>Run the search and write the resulting trace and manifest.</li>
 * </ul>
 *
 * <p>The technique name in {@link RunConfig#techniqueName()} must match a key in the
 * internal technique registry. Extend the registry as new techniques are added.
 *
 * <p>This class is a stub. The technique lookup and instantiation logic depends on
 * design decisions that have not yet been resolved.
 */
public final class ExperimentRunner {

    private final RunConfig config;

    /**
     * Constructs a runner for the given configuration.
     *
     * @param config the run configuration
     */
    public ExperimentRunner(final RunConfig config) {
        this.config = config;
    }

    /**
     * Executes the run described by the configuration.
     *
     * @throws IOException if the output directory cannot be created or the trace cannot be written
     */
    public void run() throws IOException {
        // TODO (DD-01): Implement the run orchestration:
        //               1. Look up the domain in DomainRegistry.
        //               2. Look up the technique and instantiate strategy objects.
        //               3. Construct a SinglePointHyperHeuristic (or multipoint if applicable).
        //               4. Set the problem instance (domain.loadInstance(config.instanceIndex())).
        //               5. Record start time and git commit.
        //               6. Call hyp.loadProblemDomain(problem) and hyp.run().
        //               7. Build and write the RunManifest.
        Files.createDirectories(config.outputDirectory());
        throw new UnsupportedOperationException(
                "TODO (DD-01): ExperimentRunner.run is not yet implemented. "
                + "Resolve design-decisions.md DD-01 first.");
    }
}
