package za.ac.up.cos790.instrumentation;

import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;

/**
 * Buffered CSV implementation of {@link TraceWriter}.
 *
 * <p>Writes one row per {@link TraceRecord} to a UTF-8 CSV file. The header row is
 * derived from the record's own column lists, so the schema in the file can never
 * silently drift from the record definition.
 *
 * <p>Column order: fixed columns ({@link TraceRecord#FIXED_COLUMNS}), then
 * {@code feat_*} columns in insertion order, then {@code score_*} columns in
 * insertion order.
 *
 * <p><strong>Do not add filtering that logs only interesting rows.</strong> The
 * analysis layer needs every application, including non-improving and rejected ones.
 * A surrogate model trained only on successful applications cannot learn which
 * conditions predict failure, and that is half of what this project is trying to explain.
 */
public final class CsvTraceWriter implements TraceWriter {

    private final BufferedWriter writer;
    private boolean headerWritten = false;

    /**
     * Opens (or creates) the trace file at the given path for writing.
     *
     * @param outputPath path to the CSV trace file to create or overwrite
     * @throws IOException if the file cannot be opened
     */
    public CsvTraceWriter(final Path outputPath) throws IOException {
        this.writer = Files.newBufferedWriter(
                outputPath,
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING
        );
    }

    /**
     * {@inheritDoc}
     *
     * <p>Writes the header row on the first call, then writes the data row.
     */
    @Override
    public void write(final TraceRecord record) throws IOException {
        if (!headerWritten) {
            writeHeader(record);
            headerWritten = true;
        }
        writeRow(record);
    }

    @Override
    public void close() throws IOException {
        writer.close();
    }

    private void writeHeader(final TraceRecord record) throws IOException {
        final List<String> columns = buildColumnList(record);
        writer.write(String.join(",", columns));
        writer.newLine();
    }

    private void writeRow(final TraceRecord record) throws IOException {
        final List<String> values = new ArrayList<>();

        // Fixed columns in declaration order.
        values.add(escape(record.runId()));
        values.add(Long.toString(record.iteration()));
        values.add(Integer.toString(record.heuristicId()));
        values.add(escape(record.heuristicClass()));
        values.add(Double.toString(record.depthOfSearch()));
        values.add(Double.toString(record.intensityOfMutation()));
        values.add(Integer.toString(record.targetIndex()));
        values.add(Integer.toString(record.sourceIndex()));
        values.add(Integer.toString(record.secondParentIndex()));
        values.add(Double.toString(record.objectiveBefore()));
        values.add(Double.toString(record.objectiveAfter()));
        values.add(Double.toString(record.delta()));

        // log_return: write empty field for non-finite values (NaN or Infinite)
        // rather than the literal string "NaN", which breaks Pandas dtype inference.
        // This matches design decision DD-08 and Decision 27 of the Member 1+3 spec.
        values.add(Double.isFinite(record.logReturn())
                ? Double.toString(record.logReturn())
                : "");

        values.add(Boolean.toString(record.accepted()));
        values.add(Double.toString(record.bestSoFar()));
        values.add(Double.toString(record.cpuTimeMs()));
        values.add(Double.toString(record.populationBest()));
        values.add(Double.toString(record.populationMean()));
        values.add(Double.toString(record.populationDiversity()));

        // Dynamic feature columns.
        for (final double v : record.features().values()) {
            values.add(Double.isFinite(v) ? Double.toString(v) : "");
        }

        // Dynamic score columns.
        for (final double v : record.scores().values()) {
            values.add(Double.isFinite(v) ? Double.toString(v) : "");
        }

        writer.write(String.join(",", values));
        writer.newLine();
    }

    private static List<String> buildColumnList(final TraceRecord record) {
        final List<String> columns = new ArrayList<>(TraceRecord.FIXED_COLUMNS);
        for (final String name : record.features().keySet()) {
            columns.add("feat_" + name);
        }
        for (final String name : record.scores().keySet()) {
            columns.add("score_" + name);
        }
        return columns;
    }

    private static String escape(final String value) {
        if (value == null) {
            return "";
        }
        if (value.contains(",") || value.contains("\"") || value.contains("\n")) {
            return '"' + value.replace("\"", "\"\"") + '"';
        }
        return value;
    }
}
