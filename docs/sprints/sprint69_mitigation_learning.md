# Sprint 69 — Mitigation Learning & Policy Evolution Layer

## Goal

Sprint 68 *plans and executes* mitigations; Sprint 69 closes the loop by
**learning which mitigations actually work** and evolving the policy that picks
them. It tracks measured outcomes per mitigation, updates per-strategy stats,
optimizes strategy selection, and versions the resulting policy so improvements
are explicit and replayable. This is the layer that makes the failure stack
*self-improving* rather than merely reactive. The system can now say:

- "Mitigation `pre-warm-cache` succeeded 9/11 times → raise its strategy score."
- "Strategy `reroute` now dominates `retry` for `dep-timeout` → **evolve** the
  policy to a new version."

> Confirmed by git: commit *"Sprint 69: Mitigation Learning & Policy Evolution"*
> maps to `src/allbrain/mitigation_learning/` (with `src/allbrain/policy/` as the
> policy-evolution surface).

## Architecture

```
mitigation outcomes (from Sprint 68 execution)
  ↓
OutcomeTracker          → OUTCOME_MEASURED
LearningEngine          → MITIGATION_EVALUATED
StrategyOptimizer (_score) → STRATEGY_UPDATED
PolicyStore (versioning)   → POLICY_IMPROVED
  ↓
MitigationLearningReducer → state["mitigation_learning"]
  ↓
policy/ (PolicyOptimizer, AgentSelectionPolicy, RoutingEngine) — evolved policy
```

## Scope

### In

1. New module `src/allbrain/mitigation_learning/` (`outcome_tracker`,
   `learning_engine`, `strategy_optimizer`, `policy_store`, `events`, `model`,
   `reducer`).
2. `OutcomeTracker` — record measured mitigation outcomes.
3. `LearningEngine` — evaluate mitigations against their outcomes.
4. `StrategyOptimizer` — re-score and reorder strategies from learned stats.
5. `PolicyStore` — version and persist improved policies (`PolicyVersion`).
6. Models: `OutcomeRecord`, `LearningRecord`, `StrategyStats`, `PolicyVersion`.
7. Events: `OUTCOME_MEASURED`, `MITIGATION_EVALUATED`, `STRATEGY_UPDATED`,
   `POLICY_IMPROVED`.
8. `policy/` surface (`PolicyOptimizer`, `AgentSelectionPolicy`, `RoutingEngine`)
   consuming the evolved policy.

### Out of scope (Sprint 70+)

- Cross-system / multi-agent policy sharing.
- Online gradient policy learning (Sprint 69 uses outcome-stat scoring +
  versioned policy snapshots).
- Formal verification of evolved policies before promotion.
