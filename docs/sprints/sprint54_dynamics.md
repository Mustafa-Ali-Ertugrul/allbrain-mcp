# Sprint 54 — Capability Dynamics (Drift / Trend / Forecast) Layer

## Goal

Sprint 53 made capability a *learned* scalar per `(agent, task_type)`. Sprint 54
turns that scalar into a *time series* and reasons about its motion. The system
can now say:

- "Agent `codex`'s learned capability on `implementation` has **drifted down**
  0.14 over its last observations — flag for re-evaluation."
- "Agent `qwen` shows an **improving trend** on `code_review` (positive slope,
  consistent momentum)."
- "**Forecast**: if the current trend holds, `codex` lands near 0.81 next window."

This is the first layer that treats capability as a dynamical quantity rather
than a static estimate. It is read-only over the Sprint 53 learning stream.

## Architecture

```
AGENT_CAPABILITY_LEARNED / DECAYED      (learned-capability time series)
  ↓
detect_drift()    → AGENT_CAPABILITY_DRIFT_DETECTED   (DriftLevel + magnitude)
classify_trend()  → AGENT_CAPABILITY_TREND_CLASSIFIED (TrendLabel + slope/momentum)
predict()         → AGENT_CAPABILITY_FORECAST         (forecast value + variance)
  ↓
CapabilityDynamicsManager  (threshold-gated emission)
  ↓
DynamicsReducer → state["dynamics"]  (last-wins per (agent, task_type))
```

## Scope

### In

1. New module `src/allbrain/dynamics/` (`drift`, `trend`, `forecast`, `events`,
   `model`, `manager`, `reducer`).
2. `detect_drift()` — EMA-based drift detection with observation-density weighting
   and `learning_confidence_attenuation`; classifies into `DriftLevel`.
3. `classify_trend()` — linear slope + variance + momentum + consecutive-count →
   `TrendLabel`.
4. `predict()` — sign/variance-aware forecast over the learned series.
5. Models: `DriftState`, `TrendState`, `ForecastState`.
6. New pipeline step `_dynamics_step` (off-by-default flag) reading learning
   events and emitting threshold-gated DRIFT / TREND / FORECAST events.
7. Replay binding via `state["dynamics"]` projection.

### Out of scope (Sprint 55+)

- Counterfactual capability ("what if a different agent had run this?") — Sprint 55.
- Multi-signal fusion of dynamics with other channels — Sprint 56.
- Acting on drift (re-routing / re-evaluation) — later routing/attention sprints.
- Bayesian state-space forecasting (Sprint 54 uses deterministic linear/EMA methods).
