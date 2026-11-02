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
     * Runs one or more experiments from YAML config files.
     *
     * @param args one or more config file paths
     */
    public static void main(final String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("Usage: xai-sphh <config.yaml> [config2.yaml ...]");
            System.exit(1);
        }

        final int total = args.length;
        int completed = 0;
        int failed = 0;

        for (final String arg : args) {
            final Path configPath = Path.of(arg);
            try {
                final RunConfig config = ConfigLoader.load(configPath);
                final ExperimentRunner runner = new ExperimentRunner(config);
                runner.run();
                completed++;
                System.err.printf("[%d/%d] OK: %s%n", completed + failed, total, arg);
            } catch (final Exception e) {
                failed++;
                System.err.printf("[%d/%d] FAILED: %s — %s%n",
                        completed + failed, total, arg, e.getMessage());
            }
        }
        System.err.printf("Done: %d completed, %d failed out of %d%n",
                completed, failed, total);
    }
}
