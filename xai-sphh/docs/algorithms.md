# Algorithm Specifications

Pseudocode for every algorithm currently executed by the experiment runner, transcribed
from the implementation rather than from the literature. Where the implementation departs
from the published formulation, the departure is noted.

> **Provenance.** Transcribed from the Java sources at commit `d6a3565`. This document
> describes what the code *does*, not what it ought to do. If an algorithm is changed, update
> the corresponding block here in the same commit — a report that describes an algorithm the
> runner is not executing is worse than no pseudocode at all. Two blocks carry open issues
> flagged inline (Algorithms 4 and 8); both must be resolved before the report is written.

**Conventions used throughout**

| Symbol | Meaning |
|---|---|
| `f(x)` | objective value of solution `x`. **All six domains are minimisation problems**; lower is better. |
| `H` | the pooled set of low-level heuristics exposed by the domain, indexed `0 … n−1` |
| `n` | `|H|`, the number of low-level heuristics (domain-dependent) |
| `B` | budget policy; `B.exhausted(i, t)` and `B.progress(i, t)` ∈ [0,1] |
| `x_inc` | incumbent solution | 
| `x_cand` | candidate solution produced by applying a heuristic |
| `x_best` | best solution found so far across the whole run |
| `δ` | `f(x_cand) − f(x_inc)`; **negative means improvement** |

Every algorithm below is referenced to its source file and, where one exists, to the
design-decision entry in `design-decisions.md` that justifies it.

---

## 1. Single-point selection hyper-heuristic (SPHH)

**Source:** `hyperheuristic/HyperHeuristicBase.java` (loop),
`hyperheuristic/singlepoint/SinglePointHyperHeuristic.java` (parameters)
**Decisions:** Q14 (fixed parameters), Q20 (best-so-far handling), Decision 28 (running extrema)

Techniques `SP-CF-LA`, `SP-CF-AILTA`, `SP-SR-LA` are all this loop with different
`Select` and `Accept` objects injected.

```
Algorithm 1: Single-Point Selection Hyper-Heuristic
Input:  problem domain P, selector S, acceptance criterion A, budget B
Output: best solution found

 1  allocate solution memory of size 3            // 0 = incumbent, 1 = candidate, 2 = best
 2  x_inc  <- P.initialiseSolution(0)
 3  x_best <- x_inc ;  copy x_inc into slot 2
 4  runMin <- f(x_inc) ;  runMax <- f(x_inc)      // running extrema, never the full-run range
 5  i <- 0 ;  sinceImprove <- 0 ;  sinceAccept <- 0
 6  W_delta, W_logret <- empty deques of capacity 50
 7  W_heur,  W_class  <- empty deques of capacity 3
 8
 9  while not B.exhausted(i, elapsed) do
10      state <- SnapshotState(...)                        // Section 6
11      h     <- S.select(state)                           // Algorithm 3 or 5
12      scores<- S.scoreVector()                           // NaN vector for SimpleRandom
13
14      P.setDepthOfSearch(0.1) ;  P.setIntensityOfMutation(0.1)      // fixed, Q14
15
16      t0 <- clock()
17      x_cand <- P.applyHeuristic(h, slot 0, slot 1)
18      t1 <- clock()
19      cpu <- t1 - t0                                     // times applyHeuristic ONLY
20
21      delta  <- f(x_cand) - f(x_inc)
22      logret <- LogReturn(f(x_inc), f(x_cand))           // Section 7
23
24      // Best-so-far is updated BEFORE the acceptance test: a candidate may be the
25      // best solution of the entire run and still be rejected by A.  (Q20)
26      if f(x_cand) < f(x_best) then
27          x_best <- x_cand ;  copy slot 1 into slot 2 ;  sinceImprove <- 0
28      else
29          sinceImprove <- sinceImprove + 1
30
31      runMin <- min(runMin, f(x_cand)) ;  runMax <- max(runMax, f(x_cand))
32
33      accepted <- A.accept(f(x_inc), f(x_cand), f(x_best), i)        // Algorithms 6-10
34      if accepted then
35          copy slot 1 into slot 0 ;  x_inc <- x_cand ;  sinceAccept <- 0
36      else
37          sinceAccept <- sinceAccept + 1
38
39      S.recordOutcome(h, delta, cpu)                     // Algorithm 4; no-op for SimpleRandom
40
41      WriteTraceRow(i, h, class(h), 0.1, 0.1, f(x_inc), f(x_cand),
42                    delta, logret, accepted, f(x_best), cpu,
43                    ExtractFeatures(state), scores)
44
45      push delta  onto W_delta  (capacity 50)
46      push logret onto W_logret (capacity 50)
47      push h      onto W_heur   (capacity 3)
48      push class(h) onto W_class(capacity 3)
49      i <- i + 1
50
51  copy slot 2 into slot 0        // HyFlex scores the incumbent slot, so return the best (Q20)
52  return x_best
```

**Note on line 51.** Without this copy the framework would score whatever happened to be
the incumbent when the budget expired, which for a diversifying acceptance criterion such
as Late Acceptance can be substantially worse than the best found.

---

## 2. Multi-point selection hyper-heuristic (MPHH)

**Source:** `hyperheuristic/multipoint/MultiPointHyperHeuristic.java`
**Decisions:** Decision 22 (shared selector, elitism), DD-04 Item 6 (budget scaling)

Technique `MP-CF`. Population size `p = 10` by default.

```
Algorithm 2: Multi-Point Selection Hyper-Heuristic
Input:  problem domain P, selector S, budget B, population size p
Output: best solution found

 1  allocate solution memory of size p + 1        // 0..p-1 population, p = candidate
 2  for j <- 0 to p-1 do
 3      P.initialiseSolution(j) ;  obj[j] <- f(slot j)
 4  bestSlot <- argmin_j obj[j] ;  bestVal <- obj[bestSlot]
 5  runMin <- bestVal ;  runMax <- max_j obj[j]
 6  i <- 0 ;  sinceImprove <- 0 ;  sinceAccept <- 0
 7
 8  while not B.exhausted(i, elapsed) do
 9      target <- BinaryTournamentWorst(obj)               // Algorithm 11a
10      incVal <- obj[target]
11
12      popMean <- mean(obj)
13      popDiv  <- StdDev(obj) / popMean                   // coefficient of variation; NaN if mean = 0
14      rank    <- rank of target within obj
15
16      state <- SnapshotState(..., obj[bestSlot], popMean, popDiv, rank)
17      h     <- S.select(state)
18      P.setDepthOfSearch(0.1) ;  P.setIntensityOfMutation(0.1)
19
20      t0 <- clock()
21      if h is a CROSSOVER heuristic then
22          second <- BinaryTournamentBestExcluding(obj, target)       // Algorithm 11b
23          candVal <- P.applyHeuristic(h, target, second, slot p)
24      else
25          second <- -1
26          candVal <- P.applyHeuristic(h, target, slot p)
27      t1 <- clock() ;  cpu <- t1 - t0
28
29      delta <- candVal - incVal
30
31      if candVal < bestVal then
32          bestVal <- candVal ;  sinceImprove <- 0
33      else
34          sinceImprove <- sinceImprove + 1
35
36      runMin <- min(runMin, candVal) ;  runMax <- max(runMax, candVal)
37
38      // Replacement rule doubles as the acceptance criterion: strictly better, and
39      // the population-best individual is never overwritten (elitism, Decision 22).
40      if candVal < obj[target] AND target != bestSlot then
41          copy slot p into slot target ;  obj[target] <- candVal
42          accepted <- true ;  sinceAccept <- 0
43          bestSlot <- argmin_j obj[j]                    // re-identify after replacement
44      else
45          accepted <- false ;  sinceAccept <- sinceAccept + 1
46
47      S.recordOutcome(h, delta, cpu)
48      WriteTraceRow(...)
49      i <- i + 1
50
51  return the individual with the lowest objective
```

**Note on the elitism test (line 40).** Elitism is enforced *before* the write rather than
repaired afterwards, so the best individual can never be transiently lost.

**Note on budget fairness.** By default all `p` individuals share one iteration budget, so
each receives roughly `1/p` of the heuristic applications a single-point run receives. The
`budgetScaling: per_member` option multiplies the limit by `p` to equalise per-individual
effort (Algorithm 12). Assessment 4 ran the unscaled variant; its MP-CF objective
comparisons are therefore structurally unfavourable to MP-CF.

---

## 3. Modified Choice Function — selection

**Source:** `selection/ChoiceFunction.java`
**Decisions:** DD-01 (adaptive phi from Drake, Özcan and Burke 2012), Q11 (tie-breaking), Q12 (warm-up)

```
Algorithm 3: Modified Choice Function - Select
Input:  search state (supplies n), terms f1[.], f2[.][.], f3[.], weight phi,
        previous heuristic prev, tie-breaking RNG R
Output: index of the heuristic to apply

 1  if terms are unallocated or n has changed then
 2      allocate f1[0..n-1], f2[0..n-1][0..n-1], f3[0..n-1], all zero
 3      warmup <- 0
 4
 5  // Warm-up: apply each heuristic exactly once, in ascending index order, so that
 6  // f1 holds at least one observation per heuristic before any score is used (Q12).
 7  if warmup < n then
 8      scores <- [NaN, ..., NaN]            // marks warm-up rows in the trace
 9      h <- warmup ;  warmup <- warmup + 1
10      return h
11
12  for h <- 0 to n-1 do
13      if prev >= 0 then  pairTerm <- f2[prev][h]  else  pairTerm <- 0
14      score[h] <- phi * f1[h] + phi * pairTerm + (1 - phi) * f3[h]
15
16  return ArgmaxWithRandomTieBreak(score, R)
```

```
Algorithm 3a: ArgmaxWithRandomTieBreak
 1  best <- max_h score[h]
 2  ties <- | { h : score[h] = best } |
 3  if ties = 1 then
 4      return the single h attaining best          // RNG is NOT consumed
 5  k <- R.nextInt(ties)                            // uniform over tied heuristics
 6  return the (k+1)-th heuristic attaining best, in ascending index order
```

**Note on line 14.** `f1` and `f2` share the single weight `phi`, and `f3` carries
`1 − phi`. This is the two-weight Modified Choice Function, not the three-weight
`alpha/beta/delta` form; DD-01 records why the published two-weight rule was preferred.

**Note on line 4.** The RNG is deliberately left unconsumed when there is no tie, so the
tie-breaking stream stays aligned regardless of how many unique maxima occur.

---

## 4. Modified Choice Function — update

**Source:** `selection/ChoiceFunction.java`, `recordOutcome`

```
Algorithm 4: Modified Choice Function - Update
Input:  applied heuristic h, objective delta, measured cpu time
Constants: PHI_REWARD = 0.99, PHI_DECAY = 0.01, PHI_FLOOR = 0.01, MIN_TIME = 1 ms

 1  elapsed <- max(cpu, MIN_TIME)                  // guards coarse-grained clocks
 2  reward  <- -delta / elapsed                    // improvement per unit time; delta < 0 improves
 3
 4  f1[h] <- reward + phi * f1[h]                  // exponential decay, applied heuristic only
 5
 6  if prev >= 0 then
 7      f2[prev][h] <- reward + phi * f2[prev][h]  // asymmetric: i-then-j updates f2[i][j] only (Q08)
 8
 9  for k <- 0 to n-1 do                           // f3 = idle time since last application
10      if k = h then  f3[k] <- 0  else  f3[k] <- f3[k] + elapsed
11
12  if delta < 0 then                              // improving move
13      phi <- PHI_REWARD                          // snap back: intensify
14  else
15      phi <- max(PHI_FLOOR, phi - PHI_DECAY)     // decay: shift weight towards f3, diversify
16
17  prev <- h
```

> **Open issue — wall-clock dependence.** Lines 1, 2 and 10 measure `elapsed` in
> **milliseconds of wall-clock time**. Timing jitter therefore enters heuristic selection,
> and two runs of an identical configuration on the same machine produce different results
> (verified: final objective 15.0 vs 12.0 on `SP-CF-LA_SAT_0_42`). This is faithful to the
> published formulation but prevents replication and cross-machine comparison for all three
> Choice Function techniques. See `assessment5-plan.md` section 3.5 — the fix under
> consideration replaces `elapsed` with an iteration count. **If that change is adopted, this
> pseudocode must be updated before the report is written.**

---

## 5. Simple Random selection

**Source:** `selection/SimpleRandom.java` — the baseline selector (DD-01)

```
Algorithm 5: Simple Random Selection
Input:  search state (supplies n), RNG R
Output: index of the heuristic to apply

 1  return R.nextInt(n)                    // uniform over 0..n-1

   Update:  no-op. Simple Random maintains no state and ignores all feedback.
   Scores:  the trace records a NaN vector, since no scores exist.
```

The absence of learning is the point: it isolates how much of a technique's behaviour is
attributable to adaptive selection. Assessment 4 found the `SP-SR-LA` surrogate achieves
ROC-AUC 51.75%, i.e. the 16 state features do not predict acceptance at all without the
Choice Function's adaptive selection creating structure in the search state.

---

## 6–10. Acceptance criteria

All share the interface `accept(incumbent, candidate, best, iteration) -> boolean`.

### 6. Late Acceptance (`LA`)

**Source:** `acceptance/LateAcceptance.java` — default list length `L = 50` (DD-02)

```
Algorithm 6: Late Acceptance Hill Climbing
State: circular history[0..L-1], all initialised to +infinity; head <- 0

 1  accepted <- (candidate <= incumbent) OR (candidate <= history[head])
 2  newIncumbent <- candidate if accepted else incumbent
 3  if newIncumbent < history[head] then
 4      history[head] <- newIncumbent                // tighten only; never relax the bound
 5  head <- (head + 1) mod L
 6  return accepted
```

The history initialised to `+infinity` means the first `L` iterations accept almost
everything, giving a diversifying start. Line 3 only ever lowers a history entry.

> `L = 50` is **not** a tuned optimum. DD-02 records that it was adopted because Member 2
> owned the acceptance implementation, and states that `L ∈ {1, 5, 50, 100, 500, 1000}`
> must be swept before a final value is reported.

### 7. Adaptive Iteration-Limited Threshold Accepting (`AILTA`)

**Source:** `acceptance/AILTA.java` — `INITIAL_FRACTION = 0.02`

```
Algorithm 7: AILTA
Input:  startingObjective f0 (peeked before the run), total iteration budget T
State:  threshold0 <- 0.02 * |f0|

 1  progress  <- min(1, iteration / T)       if T > 0, else 1
 2  threshold <- threshold0 * (1 - progress) // linear decay to zero at the budget end
 3  worsening <- candidate - incumbent
 4  return worsening <= threshold            // accepts bounded worsening early, pure descent late
```

The threshold is calibrated against the *initial* objective, so AILTA is scale-free across
domains without needing any domain knowledge. At `progress = 1` it degenerates to
improving-or-equal.

### 8. Simulated Annealing (`SA`)

**Source:** `acceptance/SimulatedAnnealing.java` — defaults `T0 = 1000`, decay `= 0.99`.
Retained as an ablation; **not one of the four reported techniques** (DD-02).

```
Algorithm 8: Simulated Annealing
State: temperature T <- T0

 1  delta <- candidate - incumbent
 2  if delta <= 0 then
 3      accepted <- true
 4  else if T > 0 then
 5      accepted <- (R.nextDouble() < exp(-delta / T))
 6  else
 7      accepted <- false
 8  T <- T * decayRate                       // geometric cooling, every call
 9  return accepted
```

> Line 5 uses `Math.exp`, which the Java specification permits 1 ulp of error on. Because
> the result feeds a comparison against a random draw, a 1-ulp difference can flip a
> decision and diverge the run across JVM implementations. If SA is ever promoted into the
> reported matrix, switch to `StrictMath.exp` (see `assessment5-plan.md` 7.3).

### 9. Improving or Equal (`IOE`)

**Source:** `acceptance/ImprovingOrEqual.java`

```
Algorithm 9: Improving or Equal
 1  return candidate <= incumbent            // strict descent, allowing plateau moves
```

### 10. Naive Acceptance (`NAIVE`)

**Source:** `acceptance/NaiveAcceptance.java`

```
Algorithm 10: Naive Acceptance
 1  return true                              // accepts everything; random-walk reference
```

---

## 11. Binary tournament selection (multi-point only)

**Source:** `hyperheuristic/multipoint/MultiPointHyperHeuristic.java`

```
Algorithm 11a: BinaryTournamentWorst  - choose the replacement TARGET
 1  a <- R.nextInt(p)
 2  b <- R.nextInt(p - 1) ;  if b >= a then b <- b + 1        // guarantees b != a
 3  return a if obj[a] >= obj[b] else b                       // the WORSE individual
```

```
Algorithm 11b: BinaryTournamentBestExcluding - choose the SECOND CROSSOVER PARENT
Input: index to exclude (the target)
 1  draw two distinct indices a, b from {0..p-1} \ {exclude}
 2  return a if obj[a] <= obj[b] else b                       // the BETTER individual
```

The asymmetry is deliberate: targeting the *worse* individual maximises the expected
benefit of replacement, while drawing the *better* individual as crossover partner
supplies good genetic material.

---

## 12. Budget policy

**Source:** `experiment/BudgetPolicy.java` — DD-04

```
Algorithm 12: Budget Policy
Iteration-based (used for all analysed runs):
    exhausted(i, t) = (i >= limit)
    progress(i, t)  = min(1, i / limit)

Wall-clock-based (reserved for CHeSC-protocol benchmark runs):
    exhausted(i, t) = (t >= limitMs)
    progress(i, t)  = min(1, t / limitMs)

Multi-point scaling:
    if scaling = "per_member" and budget type = iterations then
        effectiveLimit <- limit * p
    else
        effectiveLimit <- limit
```

`progress` is exposed to the state snapshot as `feat_progress` and is the axis along which
the LIME grid is constructed.

---

## 13. State snapshot and derived features

**Source:** `state/SearchState.java`, `state/FeatureExtractor.java` — Decision 28, DD-03

Constants: window `W = 50`, history length `K = 3`.

```
Algorithm 13: SnapshotState  (evaluated BEFORE the heuristic is applied)
feat_llh_count           <- n
feat_progress            <- B.progress(i, elapsed)
feat_obj_norm            <- (f(x_inc) - runMin) / (runMax - runMin)
feat_gap_to_best         <- (f(x_inc) - f(x_best)) / |f(x_best)|
feat_iters_since_improve <- sinceImprove
feat_iters_since_accept  <- sinceAccept
feat_improve_rate_50     <- fraction of the last W deltas that are negative
feat_mean_logret_50      <- mean of the last W log returns
feat_last_h1..h3         <- last K heuristic indices      (-1 when unavailable)
feat_last_class1..class3 <- last K heuristic class ordinals (-1 when unavailable)
feat_pop_diversity       <- StdDev(obj)/mean(obj)         (-1 sentinel for single-point)
feat_pop_target_rank     <- rank of target in population  (-1 sentinel for single-point)
```

**Normalisation constraint (Decision 28).** `feat_obj_norm` and `feat_gap_to_best` use
**running** observed extrema, never the full-run range. Using the full range would leak
information about the future of the run into a decision-time feature and inflate surrogate
accuracy for the wrong reason.

> The two population features are constant at the `-1` sentinel for every single-point run.
> This is what breaks the LIME discretiser for the three single-point techniques — see
> `assessment5-plan.md` 2.3.

---

## 14. Log return

**Source:** `HyperHeuristicBase.computeLogReturn` — DD-08

```
Algorithm 14: LogReturn(before, after)
 1  if before <= 0 or after <= 0 then
 2      return NaN                           // CSV writer emits an empty field, not "NaN"
 3  return ln(after / before)
```

Writing an empty field rather than the literal string `NaN` keeps Pandas dtype inference
on a float column. Near-zero objectives can still make the ratio explode, so the Python
`yates` stage clips valid log returns to `[-10, +10]` before computing summary statistics
(DD-08 extension, Item 2).

---

## Technique composition summary

| Technique | Topology | Selection | Acceptance | Algorithms used |
|---|---|---|---|---|
| `SP-SR-LA` | Single-point | Simple Random | Late Acceptance, `L=50` | 1, 5, 6 |
| `SP-CF-LA` | Single-point | Modified Choice Function | Late Acceptance, `L=50` | 1, 3, 4, 6 |
| `SP-CF-AILTA` | Single-point | Modified Choice Function | AILTA | 1, 3, 4, 7 |
| `MP-CF` | Multi-point, `p=10` | Modified Choice Function | Replacement with elitism | 2, 3, 4, 11 |

Available but not in the reported matrix: `SP-CF-SA`, `SP-SR-SA` (Algorithm 8),
`SP-*-IOE` (9), `SP-*-NAIVE` (10), `MP-SR` (5).
