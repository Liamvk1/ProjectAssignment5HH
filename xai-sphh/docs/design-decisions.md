# Design Decisions

This document records open design questions and rationale. Each entry corresponds to a
`TODO` comment in the source code.

## DD-01: Selection strategy algorithm

**File:** `selection/ChoiceFunction.java`, `selection/SimpleRandom.java`

**Question:** Which selection strategy should be the primary experimental technique?
SimpleRandom serves as a baseline. The Choice Function (Cowling, Kendall, Soubeiga 2001)
is the intended research vehicle. The weighting scheme for f1, f2 and f3 and the update
rule are open.

## DD-02: Acceptance strategy parameters

**File:** `acceptance/LateAcceptance.java`, `acceptance/SimulatedAnnealing.java`

**Question:** What are the default parameter values for Late Acceptance (list length L)
and Simulated Annealing (initial temperature, cooling schedule)? These interact with the
budget length and the domain, so they must be tuned empirically.

## DD-03: Feature set

**File:** `state/FeatureExtractor.java`, `config/features.yaml`

**Question:** Which features should be enabled by default? The full feature set is defined
in `config/features.yaml`. Features that violate the domain barrier must never be included;
the `DomainBarrierTest` enforces this. The interaction between feature count and surrogate
model complexity is an empirical question.

## DD-04: Budget policy

**File:** `experiment/BudgetPolicy.java`

**Question:** Should the default budget be time-based (milliseconds) or iteration-based
(number of heuristic applications)? Time-based budgets are fairer across domains with
different heuristic costs but are sensitive to hardware. Iteration-based budgets are
reproducible but may be unfair.

## DD-05: Surrogate model family

**File:** `python/src/xaisphh/surrogate/train.py`

**Question:** Which surrogate model family should be used to approximate the
hyper-heuristic's selection policy? A gradient-boosted tree is the default candidate
because it handles mixed types and non-linearity, and SHAP supports it natively. A linear
model would be more interpretable but less faithful.

## DD-06: SHAP vs LIME scope

**File:** `python/src/xaisphh/explain/shap_global.py`, `explain/lime_local.py`

**Question:** Should the primary explanation be global (SHAP feature importance over all
decisions) or local (LIME explanations for individual decisions at key search events)?
Both are implemented so that the choice can be made after inspecting the data.

## DD-07: f2 pair update rule

**File:** `selection/ChoiceFunctionTerms.java`

**Question:** The f2 matrix records the improvement of heuristic j when applied immediately
after heuristic i. The update rule (decay factor, windowing) is not specified in the
original paper and must be decided before the ChoiceFunction implementation is written.

## DD-08: Log return handling for non-positive objectives

**File:** `instrumentation/TraceRecord.java`

**Question:** Some problem domains may produce zero or negative objective values. The log
return is undefined in these cases. The current approach writes NaN. An alternative is a
signed log transform. This decision must be made before the Python analysis uses log returns.
