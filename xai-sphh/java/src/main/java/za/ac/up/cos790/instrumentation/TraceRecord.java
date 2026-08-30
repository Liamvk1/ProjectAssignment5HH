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
 * @param targetIndex         Solution memory slot of the individual targeted at this step.
 *                            For single-point search this is the incumbent slot (0).
 * @param sourceIndex         Solution memory slot used as the primary source. For unary
 *                            heuristics the source and target are the same slot.
 * @param secondParentIndex   Slot of the second parent for crossover heuristics, or -1
 *                            when the heuristic is not a crossover.
 * @param objectiveBefore     Incumbent objective before heuristic application.
 * @param objectiveAfter      Candidate objective after heuristic application.
 * @param delta               {@code objectiveAfter - objectiveBefore}.
 * @param logReturn           {@code log(objectiveAfter / objectiveBefore)}, or NaN
 *                            when either value is non-positive. Written as an empty
 *                            CSV field (not the literal string NaN) per DD-08.
 * @param accepted            Whether the candidate was kept (by the acceptance criterion
 *                            for single-point, or by the replacement rule for multi-point).
 * @param bestSoFar           Best objective seen up to and including this iteration.
 * @param cpuTimeMs           Wall-clock time of the heuristic application, in milliseconds.
 * @param populationBest      Best objective in the population. For single-point search
 *                            this equals {@code bestSoFar}.
 * @param populationMean      Mean objective across the population. For single-point search
 *                            this equals {@code objectiveBefore}.
 * @param populationDiversity Standard deviation of population objectives divided by their
 *                            mean. Zero for single-point search.
 * @param features            Ordered map of feature name (without prefix) to double value.
 * @param scores              Ordered map of heuristic id (as string) to double score.
 */
public record TraceRecord(
        String runId,
        long   iteration,
        int    heuristicId,
        String heuristicClass,
        double depthOfSearch,
        double intensityOfMutation,
        int    targetIndex,
        int    sourceIndex,
        int    secondParentIndex,
        double objectiveBefore,
        double objectiveAfter,
        double delta,
        double logReturn,
        boolean accepted,
        double  bestSoFar,
        double  cpuTimeMs,
        double  populationBest,
        double  populationMean,
        double  populationDiversity,
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
            "target_index",
            "source_index",
            "second_parent_index",
            "objective_before",
            "objective_after",
            "delta",
            "log_return",
            "accepted",
            "best_so_far",
            "cpu_time_ms",
            "pop_best",
            "pop_mean",
            "pop_diversity"
    );
}
