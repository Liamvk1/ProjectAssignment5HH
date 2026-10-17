package za.ac.up.cos790.acceptance;

import za.ac.up.cos790.hyperheuristic.AcceptanceStrategy;

import java.util.Random;

/**
 * Simulated Annealing acceptance strategy.
 *
 * <p>Accepts improving moves always. Accepts worsening moves with probability
 * {@code exp(-delta / temperature)}, where {@code delta} is the increase in objective
 * value and {@code temperature} decreases over time according to a geometric schedule.
 *
 * <p>This class is a stub. See design decision DD-02 for the parameter choices
 * (initial temperature and decay rate).
 */
public final class SimulatedAnnealing implements AcceptanceStrategy {

    private final double initialTemperature;
    private final double decayRate;
    private final Random rng;
    private double temperature;

    /**
     * Constructs a Simulated Annealing acceptance strategy.
     *
     * @param initialTemperature starting temperature; controls initial acceptance probability
     * @param decayRate          multiplicative decay applied each iteration (0 &lt; decayRate &lt; 1)
     * @param seed               random seed for the acceptance probability draw
     */
    public SimulatedAnnealing(final double initialTemperature,
                              final double decayRate,
                              final long seed) {
        this.initialTemperature = initialTemperature;
        this.decayRate          = decayRate;
        this.temperature        = initialTemperature;
        this.rng                = new Random(seed);
    }

    /**
     * Accepts the candidate with a probability that depends on the objective delta and
     * the current temperature.
     *
     * @param incumbentObjective current incumbent objective
     * @param candidateObjective candidate objective
     * @param bestSoFar          best objective seen (unused by this strategy)
     * @param iterationIndex     current iteration, used to advance the cooling schedule
     * @return {@code true} if the candidate should be accepted
     */
    /**
     * Accepts improving and equal moves unconditionally. Accepts worsening moves
     * with probability {@code exp(-delta / temperature)}, then applies the
     * geometric cooling schedule.
     *
     * <p>This implementation is kept as an ablation comparison against Late
     * Acceptance. It is not the baseline; Late Acceptance is preferred because it
     * requires no calibration to the objective scale (design decision DD-02).
     *
     * @param incumbentObjective current incumbent objective
     * @param candidateObjective candidate objective
     * @param bestSoFar          best objective seen (unused by this strategy)
     * @param iterationIndex     current iteration (unused; cooling is per-call)
     * @return {@code true} if the candidate should be accepted
     */
    @Override
    public boolean accept(final double incumbentObjective,
                          final double candidateObjective,
                          final double bestSoFar,
                          final long iterationIndex) {
        final double delta = candidateObjective - incumbentObjective;
        final boolean accepted;
        if (delta <= 0.0) {
            accepted = true;
        } else {
            final double probability = (temperature > 0.0)
                    ? Math.exp(-delta / temperature)
                    : 0.0;
            accepted = rng.nextDouble() < probability;
        }
        temperature *= decayRate;
        return accepted;
    }
}
