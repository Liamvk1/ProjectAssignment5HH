package za.ac.up.cos790.config;

import org.yaml.snakeyaml.Yaml;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/**
 * Reads a {@link RunConfig} from a YAML file.
 *
 * <p>The YAML keys correspond directly to the fields of {@link RunConfig}. Unknown
 * keys are silently ignored. Missing required keys cause an {@link IllegalArgumentException}.
 */
public final class ConfigLoader {

    /** Utility class; no instances required. */
    private ConfigLoader() {}

    /**
     * Loads a {@link RunConfig} from the YAML file at the given path.
     *
     * @param configPath absolute or relative path to the YAML experiment file
     * @return the populated configuration record
     * @throws IOException              if the file cannot be read
     * @throws IllegalArgumentException if a required field is absent
     */
    public static RunConfig load(final Path configPath) throws IOException {
        final Yaml yaml = new Yaml();
        try (InputStream in = Files.newInputStream(configPath)) {
            final Map<String, Object> raw = yaml.load(in);
            return parse(raw);
        }
    }

    @SuppressWarnings("unchecked")
    private static RunConfig parse(final Map<String, Object> raw) {
        final String techniqueName  = require(raw, "techniqueName",  String.class);
        final String domain         = require(raw, "domain",         String.class);
        final int    instanceIndex  = require(raw, "instanceIndex",  Integer.class);
        final long   seed           = ((Number) require(raw, "seed", Number.class)).longValue();
        final String budgetType     = require(raw, "budgetType",     String.class);
        final long   budgetValue    = ((Number) require(raw, "budgetValue", Number.class)).longValue();
        final Path   outputDir      = Path.of(require(raw, "outputDirectory", String.class));

        final Map<String, String> params = new HashMap<>();
        final Object rawParams = raw.get("techniqueParameters");
        if (rawParams instanceof Map<?, ?> m) {
            m.forEach((k, v) -> params.put(String.valueOf(k), String.valueOf(v)));
        }

        return new RunConfig(techniqueName, domain, instanceIndex, seed,
                budgetType, budgetValue, outputDir, params);
    }

    private static <T> T require(final Map<String, Object> map, final String key, final Class<T> type) {
        final Object value = map.get(key);
        if (value == null) {
            throw new IllegalArgumentException("Missing required config field: " + key);
        }
        if (!type.isInstance(value)) {
            throw new IllegalArgumentException(
                    "Config field '" + key + "' expected " + type.getSimpleName()
                            + " but got " + value.getClass().getSimpleName());
        }
        return type.cast(value);
    }
}
