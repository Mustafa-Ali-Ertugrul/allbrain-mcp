# Sprint 66 — Adaptive Recovery (Strategy Chains) Layer

## Goal

A consensus strategy (Sprint 65) is rarely a single atomic action — it is a
*chain* of recovery steps that can fail partway and need to switch strategy
mid-course. Sprint 66 executes recovery as an adaptive **strategy chain**: steps
start, succeed, or fail, and a switch policy decides when to abandon the current
strategy for the next. The system can now say:

- "Recovery chain: step `retry` failed → switch policy escalates to `reroute`
  → step `reroute` succeeded → chain complete."
- "All steps exhausted without success → adaptive recovery completed as failed."

> See the ordering note in [Sprint 64](sprint64_failure_memory.md).

## Architecture

```
consensus recovery strategy (Sprint 65)
  ↓
StrategyChain (_chain_id)            → RECOVERY_CHAIN_CREATED
step lifecycle                       → RECOVERY_STEP_STARTED
                                       RECOVERY_STEP_SUCCEEDED / RECOVERY_STEP_FAILED
LinearSwitchPolicy (on failure)      → RECOVERY_STRATEGY_SWITCHED
                                       ADAPTIVE_RECOVERY_COMPLETED
  ↓
AdaptiveRecoveryReducer → state["adaptive_recovery"]  (AdaptiveRecoveryState)
```

## Scope

### In

1. New module `src/allbrain/adaptive_recovery/` (`strategy_chain`,
   `switch_policy`, `events`, `model`, `manager`, `reducer`).
2. `StrategyChain` — ordered, restartable recovery chain with a deterministic
   `_chain_id`.
3. `LinearSwitchPolicy` — decides when to switch from a failed strategy to the
   next candidate.
4. Models: `RecoveryStep`, `RecoveryChain`, `AdaptiveRecoveryState`.
5. Events: `RECOVERY_CHAIN_CREATED`, `RECOVERY_STEP_STARTED`,
   `RECOVERY_STEP_SUCCEEDED`, `RECOVERY_STEP_FAILED`,
   `RECOVERY_STRATEGY_SWITCHED`, `ADAPTIVE_RECOVERY_COMPLETED`.

### Out of scope (Sprint 67+)

- Non-linear / cost-aware switch policies (Sprint 66 ships a linear policy;
  richer policies are future work).
- Predicting failures before a recovery is even needed — Sprint 68.
- Learning which chains succeed most and evolving policy — Sprint 69.
