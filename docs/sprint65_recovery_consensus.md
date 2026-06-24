# Sprint 65 — Recovery Consensus Layer

## Goal

Given a failure (Sprint 64), there is usually more than one candidate recovery
strategy. Sprint 65 **generates** candidate strategies and **arbitrates** among
them to reach a consensus recovery decision — reusing the arbitration paradigm of
Sprint 49 but specialized for recovery. The system can now say:

- "For this failure, candidate recoveries are `retry`, `reroute`, `degrade`;
  consensus (weighted by past success) selects `reroute`."
- "Two strategies tied; the arbiter broke the tie using prior recovery
  experience from failure memory."

> See the ordering note in [Sprint 64](sprint64_failure_memory.md): the 64–67
> sequence follows the recovery dependency chain rather than an in-code marker.

## Architecture

```
failure + retrieved recovery experience (Sprint 64)
  ↓
strategy_generator   (candidate recovery strategies)
  ↓
evaluator            (score each candidate)
  ↓
arbiter              (consensus selection)
  ↓
RecoveryConsensusReducer → state["recovery_consensus"]
```

## Scope

### In

1. New module `src/allbrain/recovery_consensus/` (`strategy_generator`,
   `evaluator`, `arbiter`, `events`, `model`, `manager`, `reducer`).
2. Candidate strategy generation from the failure context.
3. Per-candidate evaluation/scoring (informed by failure-memory recovery
   experience).
4. Consensus arbitration to select a single recovery strategy.
5. Reducer projection into `state["recovery_consensus"]`.

### Out of scope (Sprint 66+)

- Executing the chosen strategy as a multi-step chain with mid-course switching
  — Sprint 66/67 adaptive recovery.
- Predicting failures proactively — Sprint 68.
- Updating strategy preferences from measured outcomes over time — Sprint 69.
