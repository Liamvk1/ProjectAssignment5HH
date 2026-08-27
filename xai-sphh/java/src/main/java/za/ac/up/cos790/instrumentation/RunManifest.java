package za.ac.up.cos790.instrumentation;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import za.ac.up.cos790.config.RunConfig;

import java.io.IOException;
import java.net.InetAddress;
import java.net.UnknownHostException;
import java.nio.file.Path;
import java.time.Instant;

/**
 * Captures all metadata required to reproduce and identify a run.
 *
 * <p>A manifest is written as JSON to the output directory alongside the trace CSV,
 * using the same {@code runId} as a filename stem. It records enough context to
 * reconstruct the experimental conditions without consulting the calling code.
 *
 * @param runId           UUID identifying this run, matching the {@code run_id} column in the trace.
 * @param config          The full {@link RunConfig} used for this run.
 * @param gitCommitHash   The HEAD commit hash at the time of the run, or {@code "unknown"}.
 * @param hyflexVersion   The HyFlex version string as reported by the jar manifest, or {@code "unknown"}.
 * @param startTime       Wall-clock time at which the search started.
 * @param endTime         Wall-clock time at which the search ended.
 * @param machineId       Hostname of the machine on which the run executed.
 * @param finalObjective  Objective value of the best solution found.
 */
public record RunManifest(
        String runId,
        RunConfig config,
        String gitCommitHash,
        String hyflexVersion,
        Instant startTime,
        Instant endTime,
        String machineId,
        double finalObjective
) {

    private static final ObjectMapper MAPPER = buildMapper();

    /**
     * Serialises this manifest as a pretty-printed JSON file.
     *
     * @param outputPath the path at which to write the JSON file
     * @throws IOException if the file cannot be written
     */
    public void writeTo(final Path outputPath) throws IOException {
        MAPPER.writeValue(outputPath.toFile(), this);
    }

    /**
     * Returns the hostname of the current machine, or {@code "unknown"} if resolution fails.
     *
     * @return the local hostname
     */
    public static String resolveMachineId() {
        try {
            return InetAddress.getLocalHost().getHostName();
        } catch (final UnknownHostException e) {
            return "unknown";
        }
    }

    private static ObjectMapper buildMapper() {
        final ObjectMapper m = new ObjectMapper();
        m.registerModule(new JavaTimeModule());
        m.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        m.enable(SerializationFeature.INDENT_OUTPUT);
        return m;
    }
}
