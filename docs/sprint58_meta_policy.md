# Sprint 58 — Meta-Policy (Mode Selection & Reward) Layer

## Goal

The system runs in different *modes* (e.g. exploration vs. exploitation styles of
decision-making). Sprint 58 learns **which mode pays off** by estimating per-mode
reward, then selects modes with a softmax policy whose temperature and
exploration rate adapt over time. It also detects when the policy itself has
drifted (via KL divergence) and decides when to snapshot. The system can now say:

- "Mode `exploit` has the highest estimated reward (0.71); select it with
  probability 0.62 at the current temperature."
- "The policy distribution has **drifted** (KL ≥ threshold) from the last
  snapshot — take a new snapshot."

## Architecture

```
mode outcomes / reward signals
  ↓
compute_reward() → estimate_mode_reward()   → POLICY_EVALUATED
  ↓  update_mode_stats() / update_temperature() / update_exploration_rate()
select_mode()  (softmax over mode rewards)  → POLICY_UPDATED
  ↓  compute_kl_divergence() → detect_policy_drift() → should_snapshot()
POLICY_DRIFT_DETECTED
  ↓
MetaPolicyReducer → state["meta_policy"]  (PolicyState)
```

## Scope

### In

1. New module `src/allbrain/meta_policy/` (`estimator`, `evaluator`, `learner`,
   `selector`, `events`, `model`, `manager`, `reducer`).
2. `estimate_mode_reward()` / `compute_reward()` — per-mode reward estimation.
3. `select_mode()` / `_softmax_select()` — temperature-controlled softmax mode
   selection with a deterministic `_event_seed`.
4. Adaptation: `update_temperature()`, `update_exploration_rate()`,
   `update_mode_stats()`.
5. Drift: `compute_kl_divergence()`, `detect_policy_drift()`, `should_snapshot()`.
6. Models: `PolicyMode`, `ModeStats`, `RewardSignal`, `PolicyState`.
7. Events: `POLICY_EVALUATED`, `POLICY_UPDATED`, `POLICY_DRIFT_DETECTED`.

### Out of scope (Sprint 59+)

- Per-*signal* reward attribution feeding attention — Sprint 59.
- Compute/budget allocation across signals — Sprint 60 attention.
- Long-horizon policy improvement / versioning — Sprint 69 mitigation-learning
  policy evolution.
- Gradient/Bayesian policy optimization (Sprint 58 uses softmax + EMA stats).
