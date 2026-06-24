# Sprint 61 — Global Workspace Layer

## Goal

Sprint 60 budgeted attention; Sprint 61 builds the **global workspace** — the
bounded, decaying set of currently-active items that have won attention. Items
gain activation, decay over time, and the strongest are selected into the
workspace. Workspace items are then surfaced to the decision engine as
*informational* context (backward-compatible — they do not change existing
decision math). The system can now say:

- "Three items are currently active in the workspace (activation 0.8/0.6/0.5);
  the rest have decayed below threshold and were removed."
- "The decision sees these workspace items as context, but the Sprint 46
  confidence contract is unchanged."

## Architecture

```
attended signals (Sprint 60)
  ↓
compute_activation()  → WORKSPACE_ITEM_ADDED / WORKSPACE_UPDATED
apply_decay()         → (activation decays each cycle)
select_workspace_items()  → WORKSPACE_ITEM_REMOVED (below threshold)
  ↓
WorkspaceReducer → state["workspace"]  (WorkspaceState)
  ↓
DecisionEngine (workspace_items = informational, backward compat)
```

> Source marker (`decision/engine.py:28`): *"Sprint 61: workspace_items added as
> informational (backward compat)."*

## Scope

### In

1. New module `src/allbrain/workspace/` (`activation`, `decay`, `selector`,
   `events`, `model`, `manager`, `reducer`).
2. `compute_activation()` — activation scoring for candidate items (no cost field;
   cost is Sprint 60's responsibility).
3. `apply_decay()` — per-cycle activation decay.
4. `select_workspace_items()` — bounded selection of the most active items.
5. Models: `WorkspaceItem`, `WorkspaceState`.
6. Events: `WORKSPACE_ITEM_ADDED`, `WORKSPACE_UPDATED`, `WORKSPACE_ITEM_REMOVED`.
7. `DecisionEngine` integration: `workspace_items` passed as informational only.

### Out of scope (Sprint 62+)

- Episodic experience as decision input — Sprint 62.
- Semantic concepts as decision input — Sprint 63.
- Letting workspace contents change the decision score (Sprint 61 is display-only
  / backward-compatible).
