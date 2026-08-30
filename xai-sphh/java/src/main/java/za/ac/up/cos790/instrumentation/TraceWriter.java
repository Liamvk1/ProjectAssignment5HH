package za.ac.up.cos790.instrumentation;

import java.io.IOException;

/**
 * Contract for writing trace records to persistent storage.
 *
 * <p>Implementations must write a header row before the first data row and must
 * flush or close any underlying buffers when {@link #close} is called.
 *
 * <p>The column order in the output must be: fixed columns in the order defined by
 * {@link TraceRecord#FIXED_COLUMNS}, then {@code feat_*} columns in feature-name
 * order, then {@code score_*} columns in heuristic-index order.
 */
public interface TraceWriter extends AutoCloseable {

    /**
     * Writes a single trace record to the underlying output.
     *
     * @param record the trace record to write
     * @throws IOException if the underlying write operation fails
     */
    void write(TraceRecord record) throws IOException;

    /**
     * Flushes and closes the underlying output. Called once at the end of a run.
     *
     * @throws IOException if flushing or closing fails
     */
    @Override
    void close() throws IOException;
}
