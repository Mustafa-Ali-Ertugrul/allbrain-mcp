# Sprint 60 — Attention & Resource Budgeting Layer

## Goal

Compute is finite. Sprint 60 introduces an attention layer that allocates a
bounded **resource budget** across signals according to their importance
(Sprint 59) and cost, then schedules and reallocates that budget over cycles.
Cost — deliberately kept out of the Sprint 61 workspace selector — lives here.
The system can now say:

- "This cycle's budget is 1.0; allocate 0.5 to `causal`, 0.3 to `capability`,
  0.2 to `learning`; drop `dynamics` (below cutoff)."
- "Last cycle left 0.15 budget unused → derive an adaptive budget for next cycle."

## Architecture

```
AttentionSignal[importance, cost]      (from Sprint 59)
  ↓
derive_adaptive_budget() / ResourceBudget
  ↓
allocate_budget()        → ATTENTION_ALLOCATED / BUDGET_SET
schedule_attention()     (ordering within budget)
compute_unused_budget()  → BUDGET_REALLOCATED
  ↓
AttentionReducer → state["attention"]  (AttentionState)
```

> Source marker (`workspace/selector.py`): *"No cost field — cost is Sprint 60
> Attention's responsibility."*

## Scope

### In

1. New module `src/allbrain/attention/` (`allocator`, `budget`, `estimator`,
   `scheduler`, `events`, `model`, `manager`, `reducer`).
2. `allocate_budget()` — value/cost allocation of a bounded budget across signals.
3. `derive_adaptive_budget()` / `compute_unused_budget()` — adaptive budget sizing
   and reclaiming unused budget across cycles.
4. `schedule_attention()` — ordering of attended signals within the budget.
5. Models: `AttentionSignal`, `AttentionWeight`, `ResourceBudget`,
   `AttentionState`.
6. Events: `ATTENTION_ALLOCATED`, `BUDGET_SET`, `BUDGET_REALLOCATED`.

### Out of scope (Sprint 61+)

- Which attended items actually enter the decision — Sprint 61 workspace.
- Episodic/semantic memory inputs to the decision — Sprints 62/63.
- Learning the cost model from observed runtimes (Sprint 60 estimates cost; it is
  not trained here).
