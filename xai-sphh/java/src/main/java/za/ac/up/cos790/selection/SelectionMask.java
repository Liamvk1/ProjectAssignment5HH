package za.ac.up.cos790.selection;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * Phase-dependent heuristic selection mask loaded from a JSON rules file.
 *
 * <p>The mask divides the search into three phases based on budget progress:
 * <ul>
 *   <li><strong>early</strong>: progress in [0.0, 0.3)</li>
 *   <li><strong>middle</strong>: progress in [0.3, 0.7)</li>
 *   <li><strong>late</strong>: progress in [0.7, 1.0]</li>
 * </ul>
 *
 * <p>For each phase, the mask specifies which heuristic indices are allowed.
 * The rules are loaded from JSON files produced by {@code extract_rules.py}.
 */
public final class SelectionMask {

    /** Search phase enum. */
    public enum Phase { EARLY, MIDDLE, LATE }

    private static final double EARLY_UPPER  = 0.3;
    private static final double MIDDLE_UPPER = 0.7;

    private final Map<Phase, Set<Integer>> allowedByPhase;

    /**
     * Constructs a mask with explicit allowed sets per phase.
     *
     * @param allowedByPhase map from phase to allowed heuristic indices
     */
    public SelectionMask(final Map<Phase, Set<Integer>> allowedByPhase) {
        this.allowedByPhase = new EnumMap<>(Phase.class);
        for (final Phase p : Phase.values()) {
            final Set<Integer> s = allowedByPhase.getOrDefault(p, Collections.emptySet());
            this.allowedByPhase.put(p, Set.copyOf(s));
        }
    }

    /**
     * Returns the set of allowed heuristic indices for the given budget progress.
     *
     * @param budgetProgress normalised progress in [0.0, 1.0]
     * @return unmodifiable set of allowed heuristic indices
     */
    public Set<Integer> allowedHeuristics(final double budgetProgress) {
        return allowedByPhase.get(phaseOf(budgetProgress));
    }

    /**
     * Returns whether the given heuristic is allowed at the given progress.
     *
     * @param heuristicIndex the heuristic to check
     * @param budgetProgress normalised progress
     * @return true if the heuristic is allowed
     */
    public boolean isAllowed(final int heuristicIndex, final double budgetProgress) {
        return allowedByPhase.get(phaseOf(budgetProgress)).contains(heuristicIndex);
    }

    /**
     * Returns the phase for a given budget progress value.
     */
    public static Phase phaseOf(final double budgetProgress) {
        if (budgetProgress < EARLY_UPPER) return Phase.EARLY;
        if (budgetProgress < MIDDLE_UPPER) return Phase.MIDDLE;
        return Phase.LATE;
    }

    /**
     * Creates a no-op mask that allows all heuristics (0..n-1) in every phase.
     *
     * @param heuristicCount total number of heuristics
     * @return a mask that never excludes anything
     */
    public static SelectionMask allowAll(final int heuristicCount) {
        final Set<Integer> all = new HashSet<>();
        for (int i = 0; i < heuristicCount; i++) {
            all.add(i);
        }
        final Map<Phase, Set<Integer>> m = new EnumMap<>(Phase.class);
        for (final Phase p : Phase.values()) {
            m.put(p, all);
        }
        return new SelectionMask(m);
    }

    /**
     * Loads a mask from a JSON rules file produced by extract_rules.py.
     *
     * <p>Uses minimal JSON parsing (no external library dependency) since the
     * structure is fixed and simple: we extract the "allowed_heuristics" arrays
     * from the "heuristic_rules" object.
     *
     * @param rulesFile path to the JSON rules file
     * @param heuristicCount total number of heuristics in the domain (used as
     *                       fallback if the rules file has no heuristic_rules)
     * @return the loaded mask
     * @throws IOException if the file cannot be read
     */
    public static SelectionMask fromJson(final Path rulesFile, final int heuristicCount)
            throws IOException {
        final String json = Files.readString(rulesFile);
        final Map<Phase, Set<Integer>> allowed = new EnumMap<>(Phase.class);

        // Parse heuristic_rules.early.allowed_heuristics, etc.
        for (final Phase phase : Phase.values()) {
            final String phaseName = phase.name().toLowerCase();
            final Set<Integer> indices = parseAllowedHeuristics(json, phaseName);
            if (indices.isEmpty()) {
                // Fallback: allow all if parsing finds nothing (safety net)
                final Set<Integer> all = new HashSet<>();
                for (int i = 0; i < heuristicCount; i++) all.add(i);
                allowed.put(phase, all);
            } else {
                allowed.put(phase, indices);
            }
        }

        return new SelectionMask(allowed);
    }

    /**
     * Extracts the allowed_heuristics array for a given phase from the JSON string.
     * Uses simple string scanning — no JSON library needed for this fixed format.
     */
    private static Set<Integer> parseAllowedHeuristics(final String json, final String phase) {
        final Set<Integer> result = new HashSet<>();

        // Find "heuristic_rules" section
        final int hrIdx = json.indexOf("\"heuristic_rules\"");
        if (hrIdx < 0) return result;

        // Find the phase key within heuristic_rules
        final int phaseIdx = json.indexOf("\"" + phase + "\"", hrIdx);
        if (phaseIdx < 0) return result;

        // Find "allowed_heuristics" within this phase block
        final int allowedIdx = json.indexOf("\"allowed_heuristics\"", phaseIdx);
        if (allowedIdx < 0) return result;

        // Find the opening bracket of the array
        final int arrayStart = json.indexOf('[', allowedIdx);
        if (arrayStart < 0) return result;

        // Find the closing bracket
        final int arrayEnd = json.indexOf(']', arrayStart);
        if (arrayEnd < 0) return result;

        // Parse the integers from the array content
        final String arrayContent = json.substring(arrayStart + 1, arrayEnd).trim();
        if (arrayContent.isEmpty()) return result;

        for (final String token : arrayContent.split(",")) {
            final String trimmed = token.trim();
            if (!trimmed.isEmpty()) {
                result.add(Integer.parseInt(trimmed));
            }
        }

        return result;
    }

    /**
     * Parses the Rule B section from the JSON, if present.
     *
     * @param rulesFile path to the JSON rules file
     * @return the parsed RuleB, or null if no rule_b section or type is "none"
     * @throws IOException if the file cannot be read
     */
    public static RuleB parseRuleB(final Path rulesFile) throws IOException {
        final String json = Files.readString(rulesFile);

        final int rbIdx = json.indexOf("\"rule_b\"");
        if (rbIdx < 0) return null;

        // Parse type
        final int typeIdx = json.indexOf("\"type\"", rbIdx);
        if (typeIdx < 0) return null;

        final int typeValStart = json.indexOf('"', json.indexOf(':', typeIdx) + 1);
        final int typeValEnd   = json.indexOf('"', typeValStart + 1);
        final String type = json.substring(typeValStart + 1, typeValEnd);

        if ("none".equals(type) || "skipped".equals(type)) return null;

        // Parse threshold
        final int threshIdx = json.indexOf("\"threshold\"", rbIdx);
        if (threshIdx < 0) return null;

        final int colonIdx = json.indexOf(':', threshIdx);
        // Find the numeric value after the colon
        int numStart = colonIdx + 1;
        while (numStart < json.length() && (json.charAt(numStart) == ' ' || json.charAt(numStart) == '\n')) {
            numStart++;
        }
        int numEnd = numStart;
        while (numEnd < json.length() && (Character.isDigit(json.charAt(numEnd))
                || json.charAt(numEnd) == '.' || json.charAt(numEnd) == '-')) {
            numEnd++;
        }
        final double threshold = Double.parseDouble(json.substring(numStart, numEnd));

        return new RuleB(type, threshold);
    }

    /**
     * Represents a Rule B trigger parsed from the rules JSON.
     *
     * @param type      "reheat" or "diversity"
     * @param threshold the trigger threshold value
     */
    public record RuleB(String type, double threshold) {}
}
