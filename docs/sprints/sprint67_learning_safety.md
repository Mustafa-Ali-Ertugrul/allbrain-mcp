# Sprint 67 — Learning Safety Layer

## Goal

The self-improving layers (53–63) and recovery layers (64–66) all *change the
system's behavior from experience*. Sprint 67 adds the guardrails that keep that
learning safe: it maintains exploration **entropy** so the policy never collapses
to a single brittle choice, **caps** how much simulated (non-real) outcomes are
allowed to weigh on learning, and **guards** against runaway learning drift. The
system can now say:

- "Policy entropy dropped too low → **trigger exploration** to avoid premature
  convergence."
- "This update leans on simulated outcomes → **cap** its weight so imagined
  results can't dominate real ones."
- "Learning has **drifted** unsafely fast → raise a guard event."

> See the ordering note in [Sprint 64](sprint64_failure_memory.md): 64–67 follow
> the recovery/learning dependency chain; this layer hardens the learning loop
> before the predictive layers (68+).

## Architecture

```
learning / exploration signals
  ↓
EntropyCalculator (shannon_entropy / entropy_decay)
Explorer        → SAFETY_EXPLORATION_TRIGGERED   (entropy below floor)
OutcomeValidator → SAFETY_SIMULATION_WEIGHT_CAPPED (sim weight ≤ MAX_SIMULATION_WEIGHT)
DriftGuard      → SAFETY_LEARNING_DRIFT_DETECTED  (unsafe learning drift)
  ↓
LearningSafetyReducer → state["learning_safety"]
```

## Scope

### In

1. New module `src/allbrain/learning_safety/` (`entropy`, `explorer`,
   `outcome_validator`, `drift_guard`, `events`, `model`, `reducer`).
2. `shannon_entropy()` / `entropy_decay()` / `EntropyCalculator` — measure and
   track exploration entropy.
3. `Explorer` — trigger exploration when entropy falls below a floor.
4. `OutcomeValidator` — cap simulated-outcome influence at `MAX_SIMULATION_WEIGHT`.
5. `DriftGuard` — detect unsafe learning drift.
6. Models: `EntropyState`, `ExplorationDecision`, `SafetyEvent`.
7. Events: `SAFETY_EXPLORATION_TRIGGERED`, `SAFETY_SIMULATION_WEIGHT_CAPPED`,
   `SAFETY_LEARNING_DRIFT_DETECTED`.

### Out of scope (Sprint 68+)

- Predicting failures before they happen — Sprint 68.
- Learning which mitigations are best and evolving policy — Sprint 69.
- Hard rollback of unsafe learned state (Sprint 67 flags and caps; it does not
  revert prior learning).
