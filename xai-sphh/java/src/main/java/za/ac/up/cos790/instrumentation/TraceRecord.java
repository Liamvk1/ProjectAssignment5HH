package za.ac.up.cos790.instrumentation;

import java.util.List;
import java.util.Map;

/**
 * Flat data record representing one row of the trace file.
 *
 * <p>The fixed column names listed in {@link #FIXED_COLUMNS} must match the column
 * specification in {@code docs/trace-schema.md} exactly. {@code TraceSchemaTest}
 * verifies this at test time. Do not rename, reorder or remove columns without
 * updating the schema document and bumping the schema version.
 *
 * <p>Dynamic columns ({@code feat_*} and {@code score_*}) are carried in the
 * {@code features} and {@code scores} maps and are written after the fixed columns.
 *
 * @param runId               Unique identifier for the run (UUID).
 * @param iteration           Zero-based iteration counter.
 * @param heuristicId         Index of the selected low-level heuristic.
 * @param heuristicClass      HyFlex heuristic type name.
 * @param depthOfSearch       Depth-of-search parameter used at this step.
 * @param intensityOfMutation Intensity-of-mutation parameter used at this step.
 * @param objectiveBefore     Incumbent objective before heuristic application.
 * @param objectiveAfter      Candidate objective after heuristic application.
 * @param delta               {@code objectiveAfter - objectiveBefore}.
 * @param logReturn           {@code log(objectiveAfter / objectiveBefore)}, or NaN.
 * @param accepted            Whether the acceptance strategy kept the candidate.
 * @param bestSoFar           Best objective seen up to and including this iteration.
 * @param cpuTimeMs           Wall-clock time of the heuristic application, in milliseconds.
 * @param features            Ordered map of {@code feat_<name>} to double value.
 * @param scores              Ordered map of {@code score_<id>} to double value.
 */
public record TraceRecord(
        String runId,
        long iteration,
        int heuristicId,
        String heuristicClass,
        double depthOfSearch,
        double intensityOfMutation,
        double objectiveBefore,
        double objectiveAfter,
        double delta,
        double logReturn,
        boolean accepted,
        double bestSoFar,
        double cpuTimeMs,
        Map<String, Double> features,
        Map<String, Double> scores
) {

    /**
     * Ordered list of the fixed column names, matching {@code docs/trace-schema.md}.
     * Used by {@link CsvTraceWriter} to write the header row.
     */
    public static final List<String> FIXED_COLUMNS = List.of(
            "run_id",
            "iteration",
            "heuristic_id",
            "heuristic_class",
            "depth_of_search",
            "intensity_of_mutation",
            "objective_before",
            "objective_after",
            "delta",
            "log_return",
            "accepted",
            "best_so_far",
            "cpu_time_ms"
    );
}
