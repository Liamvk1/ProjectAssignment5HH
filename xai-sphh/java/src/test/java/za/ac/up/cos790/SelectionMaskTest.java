package za.ac.up.cos790;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import za.ac.up.cos790.selection.MaskedSelectionStrategy;
import za.ac.up.cos790.selection.SelectionMask;
import za.ac.up.cos790.selection.SelectionMask.Phase;
import za.ac.up.cos790.selection.ChoiceFunction;
import za.ac.up.cos790.state.SearchState;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class SelectionMaskTest {

    @Test
    void phaseOfReturnsCorrectPhase() {
        assertEquals(Phase.EARLY,  SelectionMask.phaseOf(0.0));
        assertEquals(Phase.EARLY,  SelectionMask.phaseOf(0.29));
        assertEquals(Phase.MIDDLE, SelectionMask.phaseOf(0.3));
        assertEquals(Phase.MIDDLE, SelectionMask.phaseOf(0.69));
        assertEquals(Phase.LATE,   SelectionMask.phaseOf(0.7));
        assertEquals(Phase.LATE,   SelectionMask.phaseOf(1.0));
    }

    @Test
    void allowAllPermitsEveryHeuristic() {
        final SelectionMask mask = SelectionMask.allowAll(5);
        for (int h = 0; h < 5; h++) {
            assertTrue(mask.isAllowed(h, 0.0));
            assertTrue(mask.isAllowed(h, 0.5));
            assertTrue(mask.isAllowed(h, 0.9));
        }
    }

    @Test
    void maskExcludesCorrectHeuristics() {
        final Map<Phase, Set<Integer>> allowed = new EnumMap<>(Phase.class);
        allowed.put(Phase.EARLY,  Set.of(0, 1));       // exclude 2, 3
        allowed.put(Phase.MIDDLE, Set.of(0, 1, 2));    // exclude 3
        allowed.put(Phase.LATE,   Set.of(0, 1, 2, 3)); // exclude none
        final SelectionMask mask = new SelectionMask(allowed);

        assertTrue(mask.isAllowed(0, 0.1));
        assertTrue(mask.isAllowed(1, 0.1));
        assertFalse(mask.isAllowed(2, 0.1));
        assertFalse(mask.isAllowed(3, 0.1));

        assertTrue(mask.isAllowed(2, 0.5));
        assertFalse(mask.isAllowed(3, 0.5));

        assertTrue(mask.isAllowed(3, 0.8));
    }

    @Test
    void fromJsonParsesRulesFile(@TempDir Path tempDir) throws IOException {
        final String json = """
                {
                  "variant": "SP-CF-AILTA-XAI",
                  "heuristic_rules": {
                    "early": {
                      "allowed_heuristics": [0, 1, 2],
                      "excluded_heuristics": [3, 4]
                    },
                    "middle": {
                      "allowed_heuristics": [0, 1, 2, 3],
                      "excluded_heuristics": [4]
                    },
                    "late": {
                      "allowed_heuristics": [0, 1, 2, 3, 4],
                      "excluded_heuristics": []
                    }
                  }
                }
                """;
        final Path rulesFile = tempDir.resolve("rules.json");
        Files.writeString(rulesFile, json);

        final SelectionMask mask = SelectionMask.fromJson(rulesFile, 5);

        assertEquals(Set.of(0, 1, 2), mask.allowedHeuristics(0.1));
        assertEquals(Set.of(0, 1, 2, 3), mask.allowedHeuristics(0.5));
        assertEquals(Set.of(0, 1, 2, 3, 4), mask.allowedHeuristics(0.9));
    }

    @Test
    void ruleBParsedCorrectly(@TempDir Path tempDir) throws IOException {
        final String json = """
                {
                  "heuristic_rules": {
                    "early": { "allowed_heuristics": [0, 1] },
                    "middle": { "allowed_heuristics": [0, 1] },
                    "late": { "allowed_heuristics": [0, 1] }
                  },
                  "rule_b": {
                    "type": "reheat",
                    "threshold": 779.5
                  }
                }
                """;
        final Path rulesFile = tempDir.resolve("rules.json");
        Files.writeString(rulesFile, json);

        final SelectionMask.RuleB ruleB = SelectionMask.parseRuleB(rulesFile);
        assertNotNull(ruleB);
        assertEquals("reheat", ruleB.type());
        assertEquals(779.5, ruleB.threshold(), 0.001);
    }

    @Test
    void maskedSelectorRespectsExclusions() {
        // Create a mask that only allows heuristic 0 and 1 in early phase.
        final Map<Phase, Set<Integer>> allowed = new EnumMap<>(Phase.class);
        allowed.put(Phase.EARLY,  Set.of(0, 1));
        allowed.put(Phase.MIDDLE, Set.of(0, 1, 2, 3));
        allowed.put(Phase.LATE,   Set.of(0, 1, 2, 3));
        final SelectionMask mask = new SelectionMask(allowed);

        final ChoiceFunction cf = new ChoiceFunction(42L);
        final MaskedSelectionStrategy masked = new MaskedSelectionStrategy(cf, mask, 42L);

        // Run many selections in early phase and verify only 0 or 1 are returned.
        for (int i = 0; i < 100; i++) {
            final SearchState state = SearchState.singlePoint(
                    4, i, 0.1, 100.0, 100.0, 0, 0, 100.0, 100.0,
                    List.of(), List.of(), List.of(), List.of());
            final int selected = masked.select(state);
            assertTrue(selected == 0 || selected == 1,
                    "Expected 0 or 1 but got " + selected + " at iteration " + i);
            // Feed back a dummy outcome so CF updates
            masked.recordOutcome(selected, -1.0, 1.0);
        }
    }
}
