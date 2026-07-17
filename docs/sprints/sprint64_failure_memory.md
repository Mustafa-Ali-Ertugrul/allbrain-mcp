# Sprint 64 — Failure Memory Layer

## Goal

Sprints 62–63 remembered experiences and concepts generally; Sprint 64 adds a
**failure-specialized memory**: it stores failures and the recovery experiences
that resolved (or didn't resolve) them, detects recurring **failure patterns**,
and retrieves prior recovery experience when a similar failure recurs. This is
the substrate the later recovery and prediction layers (65–68) build on. The
system can now say:

- "This timeout failure matches pattern `dep-timeout` seen 4× before; the
  recovery that worked was `retry-with-backoff`."
- "Record this new failure + its recovery outcome so the next occurrence can
  learn from it."

> Sprint ordering note: Sprints 68 (predictive_failure) and 69
> (mitigation_learning + policy) are fixed by git commit messages. Sprints 64–67
> cover `failure_memory`, `recovery_consensus`, and `adaptive_recovery`; the
> ordering here follows their dependency chain (memory → consensus → adaptive
> execution) rather than an explicit in-code marker.

## Architecture

```
failure occurrence + recovery outcome
  ↓
FailureMemoryStore.store()        → FAILURE_MEMORY_STORED
Learner (update recovery experience) → RECOVERY_EXPERIENCE_UPDATED
                                       RECOVERY_LEARNING_APPLIED
pattern detection                  → FAILURE_PATTERN_DETECTED
FailureMemoryRetriever.retrieve()  → FAILURE_MEMORY_RETRIEVED
  ↓
FailureMemoryReducer → state["failure_memory"]  (FailureMemoryState)
```

## Scope

### In

1. New module `src/allbrain/failure_memory/` (`store`, `retriever`, `learner`,
   `events`, `model`, `manager`, `reducer`).
2. `FailureMemoryStore` / `FailureMemoryRetriever` — persist and similarity-
   retrieve failure records and recovery experiences.
3. `Learner` — update recovery experience from observed recovery outcomes.
4. Pattern detection over stored failures → `FailurePattern`.
5. Models: `FailureRecord`, `RecoveryExperience`, `FailurePattern`,
   `FailureMemoryEntry`, `FailureMemoryState`.
6. Events: `FAILURE_MEMORY_STORED`, `FAILURE_MEMORY_RETRIEVED`,
   `FAILURE_PATTERN_DETECTED`, `RECOVERY_EXPERIENCE_UPDATED`,
   `RECOVERY_LEARNING_APPLIED`.

### Out of scope (Sprint 65+)

- Choosing among competing recovery strategies by consensus — Sprint 65.
- Executing a multi-step adaptive recovery chain — Sprint 66/67.
- Predicting failures before they occur — Sprint 68.
- Learning which mitigations work best over time — Sprint 69.
