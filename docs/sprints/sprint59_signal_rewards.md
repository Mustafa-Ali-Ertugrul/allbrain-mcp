# Sprint 59 — Signal-Reward Importance (Attention Input) Layer

## Goal

Sprint 55 attributed credit to signals; Sprint 58 learned mode rewards. Sprint 59
turns those rewards into a *forward-looking importance estimate per signal* — the
input the attention layer (Sprint 60) needs to decide where to spend compute. It
bridges the AttributionManager's `signal_rewards` and the MetaPolicyManager's
`mode_rewards` into a single importance read. The system can now say:

- "Signal `causal` has earned the most reward recently → estimate its importance
  high → it deserves more attention budget next cycle."
- "Signal `dynamics` has low recent reward → low importance → deprioritize."

## Architecture

```
signal_rewards (Sprint 55 AttributionManager)
mode_rewards   (Sprint 58 MetaPolicyManager)
  ↓
estimate_signal_importance()   (combine reward histories into importance)
estimate_signal_cost()         (per-signal compute cost estimate)
  ↓
AttentionSignal records  →  feeds Sprint 60 budget allocation
```

> Source marker (`attention/manager.py`): *"Reads from: signal_rewards
> (Sprint 59 AttributionManager) and mode_rewards (Sprint 58 MetaPolicyManager)."*

## Scope

### In

1. `estimate_signal_importance()` — fuses Sprint 55 signal rewards and Sprint 58
   mode rewards into a per-signal importance score (in `attention/estimator.py`).
2. `estimate_signal_cost()` — per-signal compute-cost estimate, paired with
   importance for the value/cost tradeoff in Sprint 60.
3. `AttentionSignal` model carrying importance + cost per signal.
4. Wiring of AttributionManager `signal_rewards` and MetaPolicyManager
   `mode_rewards` as the upstream inputs.

### Out of scope (Sprint 60+)

- Allocating an actual compute budget from these importances — Sprint 60.
- Scheduling / reallocation of budget across cycles — Sprint 60 scheduler.
- Feeding budgeted items into the final decision — Sprint 61 workspace.
- Learning the importance→budget mapping (Sprint 59 estimates; Sprint 60 spends).
