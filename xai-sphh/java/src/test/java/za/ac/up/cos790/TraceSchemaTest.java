package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import za.ac.up.cos790.instrumentation.TraceRecord;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

/**
 * Asserts that the fixed column list in {@link TraceRecord#FIXED_COLUMNS} matches the
 * column specification in {@code docs/trace-schema.md}.
 *
 * <p>This test reads the markdown table in the schema document and compares its column
 * names to the Java list. The two must agree exactly. If they differ, either the Java
 * record or the documentation is out of date, and the schema version must be bumped.
 */
class TraceSchemaTest {

    /** Path to the schema document, relative to the project root (parent of java/). */
    private static final Path SCHEMA_DOC = Path.of("docs/trace-schema.md");

    /**
     * Pattern that matches a markdown table row whose first cell is a backtick-quoted
     * column name, e.g. {@code | `run_id` | ... |}.
     */
    private static final Pattern COLUMN_PATTERN = Pattern.compile("^\\|\\s*`([^`]+)`\\s*\\|");

    /**
     * Asserts that the fixed column names in {@link TraceRecord#FIXED_COLUMNS} exactly
     * match the column names extracted from {@code docs/trace-schema.md}.
     */
    @Test
    void fixedColumnsMustMatchSchemaDocument() throws IOException {
        final List<String> fromDoc  = parseColumnsFromDocument();
        final List<String> fromCode = TraceRecord.FIXED_COLUMNS;

        assertFalse(fromDoc.isEmpty(), "No column names were parsed from " + SCHEMA_DOC
                + ". Check the regex or the document format.");

        assertEquals(fromDoc, fromCode,
                "Fixed columns in TraceRecord.java do not match docs/trace-schema.md. "
                + "Update whichever is out of date and bump the schema version.");
    }

    private List<String> parseColumnsFromDocument() throws IOException {
        final List<String> columns = new ArrayList<>();
        boolean inFixedTable = false;

        for (final String line : Files.readAllLines(resolveSchemaPath())) {
            if (line.contains("## Fixed columns")) {
                inFixedTable = true;
                continue;
            }
            if (inFixedTable && line.startsWith("## ")) {
                // Reached the next section; stop parsing.
                break;
            }
            if (inFixedTable) {
                final Matcher m = COLUMN_PATTERN.matcher(line);
                if (m.find()) {
                    columns.add(m.group(1));
                }
            }
        }
        return columns;
    }

    /**
     * Resolves the schema document path relative to the working directory used by Gradle.
     * Gradle runs tests with the project root as the working directory.
     */
    private static Path resolveSchemaPath() {
        return SCHEMA_DOC;
    }
}
