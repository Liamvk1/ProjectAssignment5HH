package za.ac.up.cos790.domain;

import AbstractClasses.ProblemDomain;
import AbstractClasses.ProblemDomain.HeuristicType;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Enumerates the low-level heuristics available in a HyFlex problem domain.
 *
 * <p>Heuristic metadata is read from the {@link ProblemDomain} object at runtime
 * rather than from any hardcoded table. This guarantees that the reported heuristic
 * counts and classes are accurate for the domain instance actually being used.
 *
 * <p>Do not add a hardcoded heuristic table for any domain. The point of this class
 * is to make the catalogue self-reporting.
 */
public final class HeuristicCatalogue {

    /**
     * Metadata for a single low-level heuristic.
     *
     * @param index         Zero-based index used to invoke the heuristic via HyFlex.
     * @param heuristicType The HyFlex type of the heuristic.
     */
    public record HeuristicEntry(int index, HeuristicType heuristicType) {}

    private final List<HeuristicEntry> entries;

    /**
     * Builds a catalogue by querying the given problem domain for its heuristic types.
     *
     * @param problem the HyFlex problem domain to catalogue
     */
    public HeuristicCatalogue(final ProblemDomain problem) {
        final int total = problem.getNumberOfHeuristics();
        final List<HeuristicEntry> list = new ArrayList<>(total);

        for (final HeuristicType type : HeuristicType.values()) {
            final int[] indices = problem.getHeuristicsOfType(type);
            if (indices != null) {
                for (final int idx : indices) {
                    list.add(new HeuristicEntry(idx, type));
                }
            }
        }

        // Sort by index so that the catalogue is in a stable, predictable order.
        list.sort((a, b) -> Integer.compare(a.index(), b.index()));
        this.entries = Collections.unmodifiableList(list);
    }

    /**
     * Returns all heuristic entries for the domain, sorted by index.
     *
     * @return unmodifiable list of heuristic entries
     */
    public List<HeuristicEntry> entries() {
        return entries;
    }

    /**
     * Returns the total number of low-level heuristics in the domain.
     *
     * @return heuristic count
     */
    public int size() {
        return entries.size();
    }

    /**
     * Returns the heuristic type of the heuristic at the given index.
     *
     * @param heuristicIndex zero-based heuristic index
     * @return the heuristic type
     * @throws IndexOutOfBoundsException if the index is out of range
     */
    public HeuristicType typeOf(final int heuristicIndex) {
        return entries.get(heuristicIndex).heuristicType();
    }
}
