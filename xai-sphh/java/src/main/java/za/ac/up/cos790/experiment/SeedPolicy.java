package za.ac.up.cos790.experiment;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Generates reproducible random seeds for replicated experiments.
 *
 * <p>Given a single base seed and a number of replicates, this class derives a
 * deterministic sequence of seeds so that experiments are reproducible even when
 * the replication count changes between runs.
 */
public final class SeedPolicy {

    private final long baseSeed;
    private final int replicates;

    /**
     * Constructs a seed policy for the given base seed and number of replicates.
     *
     * @param baseSeed   the root seed from which all replicate seeds are derived
     * @param replicates the number of independent replicates to generate seeds for
     */
    public SeedPolicy(final long baseSeed, final int replicates) {
        this.baseSeed   = baseSeed;
        this.replicates = replicates;
    }

    /**
     * Returns a list of {@code replicates} seeds derived deterministically from the base seed.
     *
     * @return list of seeds, one per replicate
     */
    public List<Long> seeds() {
        final List<Long> result = new ArrayList<>(replicates);
        final Random rng = new Random(baseSeed);
        for (int i = 0; i < replicates; i++) {
            result.add(rng.nextLong());
        }
        return result;
    }
}
