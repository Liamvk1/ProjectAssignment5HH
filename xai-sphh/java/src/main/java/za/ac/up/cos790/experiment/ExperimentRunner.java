package za.ac.up.cos790.experiment;

import AbstractClasses.ProblemDomain;
import za.ac.up.cos790.acceptance.AILTA;
import za.ac.up.cos790.acceptance.ImprovingOrEqual;
import za.ac.up.cos790.acceptance.LateAcceptance;
import za.ac.up.cos790.acceptance.NaiveAcceptance;
import za.ac.up.cos790.acceptance.SimulatedAnnealing;
import za.ac.up.cos790.config.RunConfig;
import za.ac.up.cos790.domain.DomainRegistry;
import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;
import za.ac.up.cos790.hyperheuristic.SelectionStrategy;
import za.ac.up.cos790.hyperheuristic.multipoint.MultiPointHyperHeuristic;
import za.ac.up.cos790.hyperheuristic.singlepoint.SinglePointHyperHeuristic;
import za.ac.up.cos790.instrumentation.RunManifest;
import za.ac.up.cos790.selection.ChoiceFunction;
import za.ac.up.cos790.selection.SimpleRandom;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Map;

/**
 * Orchestrates the execution of a single hyper-heuristic run as described by a
 * {@link RunConfig}.
 *
 * <p>Supported technique names (format: {@code [SP|MP]-[CF|SR][-acceptance]}):
 * <ul>
 *   <li>{@code SP-CF-LA}    – Single-point, Choice Function, Late Acceptance</li>
 *   <li>{@code SP-CF-AILTA} – Single-point, Choice Function, AILTA</li>
 *   <li>{@code SP-CF-SA}    – Single-point, Choice Function, Simulated Annealing</li>
 *   <li>{@code SP-SR-LA}    – Single-point, Simple Random, Late Acceptance</li>
 *   <li>{@code SP-SR-AILTA} – Single-point, Simple Random, AILTA</li>
 *   <li>{@code SP-SR-SA}    – Single-point, Simple Random, Simulated Annealing</li>
 *   <li>{@code MP-CF}       – Multi-point, Choice Function (no acceptance strategy)</li>
 *   <li>{@code MP-SR}       – Multi-point, Simple Random (no acceptance strategy)</li>
 * </ul>
 *
 * <p>Optional {@code techniqueParameters} keys:
 * <ul>
 *   <li>{@code listLength}      – Late Acceptance list length L (default 50)</li>
 *   <li>{@code initialTemp}     – Simulated Annealing starting temperature (default 1000.0)</li>
 *   <li>{@code decayRate}       – Simulated Annealing geometric cooling factor (default 0.99)</li>
 *   <li>{@code totalIterations} – Estimated iterations for AILTA decay when using time budget</li>
 *   <li>{@code populationSize}  – Multi-point population size (default 10)</li>
 * </ul>
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
     * @throws IOException if the output directory cannot be created or trace/manifest cannot be written
     * @throws IllegalArgumentException if the technique name or domain is not recognised
     */
    public void run() throws IOException {
        Files.createDirectories(config.outputDirectory());

        final BudgetPolicy budget = BudgetPolicy.fromConfig(config.budgetType(), config.budgetValue());

        // Build output paths from run parameters so they are stable across reruns.
        final String stem = config.techniqueName() + "_" + config.domain()
                + "_" + config.instanceIndex() + "_" + config.seed();
        final Path tracePath    = config.outputDirectory().resolve("trace_" + stem + ".csv");
        final Path manifestPath = config.outputDirectory().resolve("manifest_" + stem + ".json");

        // Instantiate and configure the problem domain.
        final ProblemDomain problem = DomainRegistry.get(config.domain()).factory().get();
        problem.loadInstance(config.instanceIndex());

        // Peek at an initial solution so AILTA can calibrate its starting threshold.
        // We do this before loadProblemDomain so the domain is already loaded.
        problem.setMemorySize(1);
        problem.initialiseSolution(0);
        final double initialObjective = problem.getFunctionValue(0);

        // Total iterations estimate: exact for iteration budgets, configurable for time budgets.
        final long totalIterations = "iterations".equalsIgnoreCase(config.budgetType())
                ? config.budgetValue()
                : parseLong(config.techniqueParameters(), "totalIterations", 100_000L);

        // Build the hyper-heuristic.
        final var hh = buildHyperHeuristic(tracePath, budget, initialObjective, totalIterations);

        // setTimeLimit is required by the real HyFlex loadProblemDomain/run() protocol.
        // For time budgets: use the configured value. For iteration budgets: use a generous
        // wall-clock cap so the framework timer never interferes with our BudgetPolicy.
        final long timeLimitMs = "time".equalsIgnoreCase(config.budgetType())
                ? config.budgetValue()
                : parseLong(config.techniqueParameters(), "wallClockCapMs", 3_600_000L);
        hh.setTimeLimit(timeLimitMs);

        // Run: loadProblemDomain stores the domain and calls solve() via run().
        final Instant startTime = Instant.now();
        hh.loadProblemDomain(problem);
        hh.run();
        final Instant endTime = Instant.now();

        // HyperHeuristicBase copies best-so-far to slot 0 at the end of solve().
        final double finalObjective = problem.getFunctionValue(0);

        // Write run manifest alongside the trace CSV.
        final RunManifest manifest = new RunManifest(
                stem, config,
                resolveGitCommit(), resolveHyflexVersion(),
                startTime, endTime,
                RunManifest.resolveMachineId(),
                finalObjective);
        manifest.writeTo(manifestPath);
    }

    // -------------------------------------------------------------------------
    // Hyper-heuristic factory
    // -------------------------------------------------------------------------

    private AbstractClasses.HyperHeuristic buildHyperHeuristic(
            final Path tracePath,
            final BudgetPolicy budget,
            final double initialObjective,
            final long totalIterations) {

        final Map<String, String> params = config.techniqueParameters();
        final long seed = config.seed();
        final String technique = config.techniqueName();

        // Parse the technique name: [SP|MP]-[CF|SR][-acceptance]
        final String[] parts = technique.split("-", 3);
        if (parts.length < 2) {
            throw new IllegalArgumentException(
                    "Invalid technique name '" + technique
                    + "'. Expected format: [SP|MP]-[CF|SR][-acceptance].");
        }
        final String mode      = parts[0].toUpperCase();
        final String selection = parts[1].toUpperCase();
        final String acceptance = (parts.length >= 3) ? parts[2].toUpperCase() : "";

        final SelectionStrategy selector = switch (selection) {
            case "CF" -> new ChoiceFunction(seed);
            case "SR" -> new SimpleRandom(seed);
            default   -> throw new IllegalArgumentException(
                    "Unknown selection component '" + selection + "' in '" + technique + "'.");
        };

        if ("MP".equals(mode)) {
            final int popSize = parseInt(params, "populationSize",
                    MultiPointHyperHeuristic.DEFAULT_POPULATION_SIZE);
            return new MultiPointHyperHeuristic(seed, tracePath, budget, selector, popSize);
        }

        if (!"SP".equals(mode)) {
            throw new IllegalArgumentException(
                    "Unknown mode '" + mode + "' in '" + technique + "'. Expected SP or MP.");
        }

        final AcceptanceStrategy acceptor = switch (acceptance) {
            case "LA"    -> new LateAcceptance(
                                parseInt(params, "listLength", LateAcceptance.DEFAULT_LIST_LENGTH));
            case "AILTA" -> new AILTA(initialObjective, totalIterations);
            case "SA"    -> new SimulatedAnnealing(
                                parseDouble(params, "initialTemp",  1_000.0),
                                parseDouble(params, "decayRate",    0.99),
                                seed);
            case "IOE"   -> new ImprovingOrEqual();
            case "NAIVE" -> new NaiveAcceptance();
            default      -> throw new IllegalArgumentException(
                    "Unknown acceptance component '" + acceptance + "' in '" + technique + "'.");
        };

        return new SinglePointHyperHeuristic(seed, tracePath, budget, selector, acceptor);
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static int parseInt(final Map<String, String> p, final String key, final int def) {
        final String v = p.get(key);
        return (v != null) ? Integer.parseInt(v) : def;
    }

    private static long parseLong(final Map<String, String> p, final String key, final long def) {
        final String v = p.get(key);
        return (v != null) ? Long.parseLong(v) : def;
    }

    private static double parseDouble(final Map<String, String> p, final String key, final double def) {
        final String v = p.get(key);
        return (v != null) ? Double.parseDouble(v) : def;
    }

    /** Returns the HEAD git commit hash, or {@code "unknown"} if unavailable. */
    private static String resolveGitCommit() {
        try {
            final Process p = new ProcessBuilder("git", "rev-parse", "HEAD")
                    .redirectErrorStream(true)
                    .start();
            try (final InputStream is = p.getInputStream()) {
                final String hash = new String(is.readAllBytes()).trim();
                return hash.isEmpty() ? "unknown" : hash;
            }
        } catch (final Exception e) {
            return "unknown";
        }
    }

    /** Returns the HyFlex jar's Implementation-Version attribute, or {@code "unknown"}. */
    private static String resolveHyflexVersion() {
        try {
            final var src = ProblemDomain.class.getProtectionDomain().getCodeSource();
            if (src == null) return "unknown";
            try (final var jar = new java.util.jar.JarFile(src.getLocation().getFile())) {
                final String v = jar.getManifest().getMainAttributes()
                        .getValue("Implementation-Version");
                return (v != null) ? v : "unknown";
            }
        } catch (final Exception ignored) {
            return "unknown";
        }
    }
}
