package za.ac.up.cos790;

import za.ac.up.cos790.config.ConfigLoader;
import za.ac.up.cos790.config.RunConfig;
import za.ac.up.cos790.experiment.ExperimentRunner;

import java.nio.file.Path;

/**
 * Entry point for the xai-sphh application.
 *
 * <p>Accepts a single command-line argument: the path to a YAML experiment configuration
 * file. Loads the configuration and delegates entirely to {@link ExperimentRunner}.
 */
public final class Main {

    /** Utility entry-point class; no instances required. */
    private Main() {}

    /**
     * Parses the config path from {@code args[0]} and hands off to {@link ExperimentRunner}.
     *
     * @param args command-line arguments; {@code args[0]} must be the config file path
     */
    public static void main(final String[] args) throws Exception {
        if (args.length != 1) {
            System.err.println("Usage: xai-sphh <path-to-config.yaml>");
            System.exit(1);
        }

        final Path configPath = Path.of(args[0]);
        final RunConfig config = ConfigLoader.load(configPath);
        final ExperimentRunner runner = new ExperimentRunner(config);
        runner.run();
    }
}
