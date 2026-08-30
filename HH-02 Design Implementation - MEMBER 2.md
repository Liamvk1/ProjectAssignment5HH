## Task

Implement the heuristic selection rule and the move acceptance criterion for a HyFlex-based single point selection perturbative hyper-heuristic. This covers how low-level heuristics are scored and chosen, how their parameters are set, how the second parent for a crossover heuristic is obtained, when the search restarts, whether a candidate solution is kept, and how the best solution found is tracked. Population management, state feature extraction and trace writing are supplied by other members and are not in scope here.

Java 21, Gradle, HyFlex vendored under `lib/hyflex/`. UK English. Do not use dashes as sentence punctuation in code, comments or documentation.

## Background you need in order to make correct choices

A selection perturbative hyper-heuristic starts from a complete candidate solution and repeatedly chooses a low-level perturbative heuristic to apply to it. The component built here is the part that makes that choice and then decides whether to keep the result. Everything else in the run exists to feed it or to record it.

The research contribution is not the search but the explanation of it, and that has one consequence which overrides ordinary engineering instinct. The controller must be learnable. A surrogate model is later trained to reproduce the selection rule from the logged state, so a deterministic rule that a model can recover exactly is worth more here than a stochastic rule that performs slightly better. Where a choice existed between a rule that searches marginally better and a rule that can be explained faithfully, the explainable rule was taken. This is why selection is a plain argmax rather than roulette wheel or epsilon greedy, and why restarts are off by default.

The hyper-heuristic must not observe anything problem specific. This is the domain barrier. The search may see only the number of low-level heuristics available, their class, and the objective values that result from applying them. No heuristic index, heuristic count or class mapping may be hardcoded for any domain, because the same controller runs unchanged across all six CHeSC domains.

Those six domains have objective values that differ by orders of magnitude. A parameter calibrated to the scale of one domain is meaningless in another. This single constraint drives more of the decisions below than any other consideration, and it is the reason Late Acceptance was chosen over simulated annealing, the reason the heuristic parameters are held at the value HyFlex itself documents, and the reason no threshold in this component is expressed in objective units.

Two rules were applied to the literature. Published constants are used as published and attributed. Where a paper does not state a value, no value is invented and attributed to it. Anything assumed is marked in the entry as an assumption.

## Question to entry map

Entries are numbered by the design question they answer, so Q08 answers question 8. This matches the numbering used for questions 21 to 31, so a question number is the same reference in both documents.

| Question | Topic | Entry |
| --- | --- | --- |
| 8 | Which choice function terms are used | Q08 |
| 9 | How the weights are set | Q09 |
| 10 | How improvement is measured | Q10 |
| 11 | The selection rule | Q11 |
| 12 | How the choice function is initialised | Q12 |
| 13 | Where the second crossover parent comes from | Q13 |
| 14 | Heuristic parameters (depth of search, intensity of mutation) | Q14 |
| 15 | Which heuristics are in the pool | Q15 |
| 16 | Restart policy | Q16 |
| 17 | Acceptance criterion | Q17 |
| 18 | The list length L | Q18 |
| 19 | What the candidate is compared against | Q19 |
| 20 | Best-so-far tracking | Q20 |

## Q08: which choice function terms are used

**File:** `selection/ChoiceFunction.java`, `selection/ChoiceFunctionTerms.java`

**Decision.** All three terms: f1 (how well a heuristic has done on its own), f2 (how well
it has done immediately after each other heuristic), and f3 (how long since it was last
used).

**Reason.** The published definition uses all three. Two things in this repository already
assume f2 exists: `ChoiceFunctionTerms` carries an n x n matrix, and the feature set logs
`last_heuristic_0`, `last_heuristic_1` and `last_heuristic_2`. If the controller ignored
the previous heuristic, those three features could not explain any decision, and the
explanation work later in the project would be built on columns that carry no signal.

**Consequence.** The score is a weighted sum of three terms. f2 is looked up as
`f2[k][h]`, where k is the heuristic applied at the previous step. Before the first
application k is -1 and the pair term contributes zero.

## Q09: how the weights are set

**File:** `selection/ChoiceFunctionWeights.java`

**Decision.** Adaptive weights, using the Modified Choice Function rule, as the default.
A single value phi weights both f1 and f2 and is also their decay. On an improving move phi
snaps back to 0.99; otherwise it drops by 0.01 with a floor of 0.01. The f3 weight is
1 - phi. Static weights remain available for ablation but must be given explicitly in the
configuration file.

**Reason.** The Modified Choice Function was designed and tested on HyFlex across all six
CHeSC domains, and its constants are published, so no per-domain tuning is needed and a run
is reproducible from the configuration alone. Cowling, Kendall and Soubeiga did not publish
the numeric values they used for the original static weights, so the code must not invent
values and present them as theirs.

**Consequence.** Static mode has no silent defaults: if `selection.weights: static` is set
without values, construction fails rather than guessing. The project's own fallback values
are documented as project defaults, not as published ones.

**Assumption.** Neither Modified Choice Function paper states phi's starting value. This
code starts it at the reward value, 0.99, so the search begins by intensifying. This is an
assumption and is recorded as one.

## Q10: how improvement is measured

**File:** `selection/ChoiceFunction.java`, `hyperheuristic/ObjectiveSense.java`

**Decision.** Improvement per unit of CPU time: the objective gain divided by the
milliseconds the heuristic took, with the time floored at a small configurable minimum.

**Reason.** This matches the ratio in the published definition. It also matters under a
time budget: a heuristic that gains a little in one millisecond is more useful than one
that gains slightly more in a hundred. The floor stops a fast heuristic on a coarse clock
from producing a division by zero.

**Consequence.** Sign handling is centralised in `ObjectiveSense`. Under minimisation the
reward is `before - after`, which is deliberately the opposite sign to the `delta` column
in the trace. Anyone reading reward and delta together must keep that in mind.

## Q11: the selection rule

**File:** `selection/ChoiceFunction.java`

**Decision.** Take the highest-scoring heuristic. Break ties with a random draw from a
stream derived from the run seed. Lowest-index tie-breaking is available for fully
deterministic runs.

**Reason.** Argmax is what the Choice Function specifies. It is also the rule this project
can explain: a surrogate model can recover a deterministic argmax policy exactly, whereas
roulette-wheel or epsilon-greedy selection inject randomness that puts a ceiling on how
faithful any explanation can be. Ties are not a corner case here; at iteration zero every
score is equal.

**Consequence.** The tie-break stream is derived by name, so adding another random
component later does not shift this one and break reproducibility of earlier runs.

## Q12: how the choice function is initialised

**File:** `selection/ChoiceFunction.java`

**Decision.** A warm-up pass that applies each pooled heuristic once, in ascending index
order, before scoring begins. Warm-up iterations come out of the ordinary budget.

**Reason.** Scoring is meaningless while some f1 entries have never been observed. Applying
each heuristic once costs a number of iterations equal to the pool size, against a budget
of tens of thousands, and removes the arbitrary choice of what an unobserved heuristic is
worth.

**Consequence.** Warm-up iterations go through acceptance and best-so-far tracking like any
other iteration, and are written to the trace. They are identifiable because their whole
score block is NaN, so no extra trace column is needed. A zero initialisation and an
optimistic initialisation are also implemented; optimistic is scale-dependent and is
documented as unsuitable for cross-domain work.

## Q13: where the second crossover parent comes from

**File:** `hyperheuristic/SecondParentPolicies.java`

**Decision.** An elite memory of the ten best solutions found. The second parent is a
uniformly random member of that memory. Every tenth crossover call bypasses the memory and
uses a freshly initialised solution instead. A new solution replaces the worst memory entry
if it is better and not already present.

**Reason.** This is the only crossover management scheme evaluated across all six CHeSC
domains, and it moved the Modified Choice Function from 38.85 to 73.70 CHeSC points. The
periodic fresh solution stops the memory converging on near-identical solutions, which
would make crossover behave like a copy.

**Consequence.** The memory needs its own solution slots, so the search loop enlarges the
HyFlex memory before searching. `best_so_far`, `fresh_random` and `none` are available as
configuration alternatives.

**Documented deviation.** The paper updates the memory only from crossover outputs. In a
domain where crossover is rarely selected, the memory then barely moves. The default here
updates the memory from any accepted-or-rejected candidate, so it really does hold the best
solutions seen. Set `crossover.eliteUpdateSource: crossover_only` to reproduce the paper.

## Q14: heuristic parameters (depth of search, intensity of mutation)

**File:** `hyperheuristic/HeuristicParameterPolicy.java`

**Decision.** Fixed at 0.1 for both, for the baseline.

**Reason.** The HyFlex documentation gives 0.1 as the default operation of the low-level
heuristics, so this is the domain authors' own value rather than one chosen here. Holding
the parameters fixed keeps the baseline clean: any difference in outcome is attributable to
selection and acceptance rather than to a parameter that was also moving.

**Consequence.** Both values are still written to every trace row, so the columns exist and
are constant rather than absent. An eleven-level discretisation (0.0 to 1.0 in steps of
0.1) is implemented and available for the improvement phase. Making the parameter level
part of the selection decision would multiply the number of arms by eleven, which is
deferred rather than adopted quietly.

## Q15: which heuristics are in the pool

**File:** `hyperheuristic/HeuristicPool.java`

**Decision.** All four classes, including crossover.

**Reason.** Crossover is normally excluded because there is no natural second parent.
Q13 solves that, so there is no longer a reason to discard a whole class of operators.

**Consequence.** The pool is built at run time from `getNumberOfHeuristics()` and
`getHeuristicsOfType()`. No heuristic index is hard-coded anywhere. Domains that do not
implement a class return null rather than an empty array, and that is handled. Indices with
no reported class are labelled UNKNOWN rather than dropped.

## Q16: restart policy

**File:** `hyperheuristic/RestartPolicy.java`

**Decision.** No restarts by default. A stagnation-threshold restart is implemented and can
be switched on in the configuration.

**Reason.** Late Acceptance already provides diversification, so adding restarts on top
means two mechanisms doing the same job and no way to tell which one mattered. More
importantly for this project, a restart makes the objective jump for a reason no heuristic
caused. The explanation layer would then be asked to attribute a change that the controller,
not the heuristic, produced.

**Consequence.** When restarts are enabled they reset only the working solution and the
acceptance history. They never reset the best-so-far solution, the selection statistics, the
trace, or any random stream.

**Open issue.** There is no trace column for restart events. They are written to the Java
logger only. If restarts are used in a reported experiment, the schema needs a column.

## Q17: acceptance criterion

**File:** `acceptance/LateAcceptance.java`

**Decision.** Late Acceptance Hill Climbing.

**Reason.** It only ever compares two objective values, so it needs no calibration to the
scale of the objective. That is decisive here: the six CHeSC domains have objective values
that differ by orders of magnitude, and a simulated annealing temperature that works on one
would be meaningless on another. It also has one parameter instead of three, and it is
deterministic, so the accept-or-reject rule is something a surrogate model can learn.

**Consequence.** Simulated annealing is implemented as an ablation, with a geometric
cooling schedule and an optional auto-scaled starting temperature, but it is not the
baseline.

## Q18: the list length L

**File:** `acceptance/LateAcceptance.java`

**Decision.** L = 50, configurable through `acceptance.L`.

**Reason.** L controls how much worsening the search tolerates: small L is close to hill
climbing, large L accepts far more. 50 is a middle value that is not tuned to any one
domain. It is a starting point, not a justified optimum.

**Consequence.** The constant lives in exactly one place. An `acceptanceRate()` diagnostic
is exposed so the sweep over {1, 5, 50, 100, 500, 1000} needed to justify a final value can
be run and reported.

## Q19: what the candidate is compared against

**File:** `acceptance/LateAcceptance.java`

**Decision.** Accept if the candidate is no worse than the current solution, or better than
the objective recorded L iterations ago. Never compare against the best-so-far solution.

**Reason.** This is the published rule. Comparing against best-so-far would turn the
criterion into a strict hill climb on the best value, which is not Late Acceptance and would
remove the escape mechanism the method exists to provide.

**Consequence.** The `bestSoFar` argument in the acceptance interface is deliberately unused
by this implementation, and a test asserts that changing it cannot change the decision. The
history entry is updated only when the current solution is better than what is stored there,
which is what stops a rejected worsening move from poisoning the list.

## Q20: best-so-far tracking

**File:** `hyperheuristic/HyperHeuristicBase.java`

**Decision.** Three separate solution slots: incumbent (0), candidate (1), best-so-far (2).
Best-so-far is updated from the candidate, even when acceptance rejects that candidate. At
the end of the run the best slot is copied into the incumbent slot.

**Reason.** The acceptance criterion deliberately accepts worsening moves, so the working
solution is often not the best one seen. A good solution found and then walked away from
must still be kept, because that is the value HyFlex scores the run on. Updating from the
candidate rather than from the accepted solution matters: a candidate can be the best
solution of the whole run and still be rejected by the acceptance rule.

**Consequence.** The final copy means the run result is the best solution found, not
whatever was held when the budget expired. Slots 3 and upwards belong to the second-parent
policy, so the loop enlarges the HyFlex memory before searching rather than relying on the
default size of two.

## Tests

Seventy assertions across five test classes, all passing.

- Warm-up applies each pooled heuristic exactly once, in index order, and draws on the ordinary budget rather than a budget of its own.
- The reward has the correct sign under both objective senses, and is floored rather than dividing by a zero elapsed time.
- f2 conditions on the heuristic applied at the previous step and is asymmetric, so the pair term is not a second copy of f1.
- The adaptive weight snaps back to the reward value on an improving move and never falls below its floor.
- Tie-breaking is reproducible under a seed and can reach every tied heuristic, and lowest-index tie-breaking ignores the seed entirely.
- Excluded heuristics are never selected and never applied, and the score vector still spans the whole domain so trace columns line up.
- Late Acceptance compares the candidate against the objective from L steps ago, and changing the best-so-far argument cannot change the decision.
- The acceptance history is updated only when the current solution improves on the stored value, so a rejected worsening move cannot poison the list.
- Crossover uses the binary overload with two distinct source slots, and the candidate slot never aliases a parent.
- The elite memory uses a freshly initialised solution on every m-th call, replaces the worst entry, and rejects duplicates.
- Best-so-far is banked from the candidate even when the acceptance criterion rejects that candidate.
- The run reports the best solution found rather than the working solution held when the budget expired.
- A restart rebuilds the working solution without losing the best-so-far objective, and restarts are off by default.
- Heuristic parameters stay on the eleven discrete levels, are clamped at the boundaries, and are reproducible from a seed.
- The pool is built from the domain at runtime and handles a domain that returns null for a heuristic class it does not implement.

## Acceptance criteria

1. Every decision is recorded as decision, reason and consequence, with published values attributed and every assumption marked as one.
2. No numeric constant is attributed to a paper that does not state it.
3. No heuristic index, heuristic count or class mapping is hardcoded for any domain.
4. The multi-point technique can share the same `SelectionStrategy` instance without modification, so the single point and multi-point comparison holds the selector constant.
5. Every configuration option has a working default, so a run starts without tuning, and an unrecognised option is reported rather than ignored.
6. The acceptance criterion contains no threshold expressed in objective units.
7. `./gradlew test` passes.

