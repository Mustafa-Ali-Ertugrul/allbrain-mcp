# Sprint 55 — Counterfactual Signal Attribution Layer

## Goal

By Sprint 54 the system produced multiple signals (capability, learning,
dynamics, causal) but could not say *which signal earned the outcome*. Sprint 55
adds credit assignment: given a decision's reward, it allocates that reward
across the contributing signal channels using a blend of **proportional** and
**counterfactual** weighting. The system can now say:

- "This success was 0.55 capability, 0.25 causal, 0.15 learning, 0.05 dynamics."
- "Counterfactually, removing the *causal* signal would have changed the outcome
  most — its credit is upweighted."
- "The importance of the `dynamics` signal **shifted** beyond threshold — surface it."

## Architecture

```
task outcome (decision_id, reward, signal contributions)
  ↓
allocate_credit()   (0.70 proportional + counterfactual share × 0.5 confidence)
  │  estimate_signal_impact() ── read-only reuse of Sprint 55 causal intervention
  ↓
SIGNAL_CREDIT_ASSIGNED        (per-signal allocation)
  ↓  EMA (α = 0.10) per signal
SIGNAL_ATTRIBUTION_UPDATED    (rolling signal reward + observation count)
  ↓  detect_importance_change() with hysteresis
SIGNAL_IMPORTANCE_CHANGED     (delta ≥ 0.10)
  ↓
AttributionReducer → state["attribution"]
```

## Scope

### In

1. New module `src/allbrain/attribution/` (`allocator`, `counterfactual`,
   `matrix`, `events`, `model`, `manager`, `reducer`).
2. `allocate_credit()` — blends `ATTRIBUTION_PROPORTIONAL_WEIGHT` (0.70) with
   counterfactual scores downweighted by `ATTRIBUTION_CF_CONFIDENCE` (0.5);
   `ATTRIBUTION_MIN_CONTRIBUTION` (0.05) floor with redistribution.
3. `estimate_signal_impact()` — read-only reuse of the causal
   `simulate_intervention()` ("this signal olmasa outcome ne olurdu?").
4. `detect_importance_change()` — hysteresis-gated importance tracking
   (`ATTRIBUTION_IMPORTANCE_THRESHOLD` 0.10).
5. Models: `CreditAllocation`, `AttributionResult`.
6. Pipeline step (~`pipeline.py:2026`): reads task-outcome events, runs
   counterfactual attribution; CF re-estimation every
   `ATTRIBUTION_COUNTERFACTUAL_INTERVAL` (10) calls.

### Out of scope (Sprint 56+)

- Fusing the attributed weights back into a single decision score — Sprint 56.
- Mode/policy reward estimation (which *mode* earned the outcome) — Sprint 58.
- Per-signal reward feeding attention budgets — Sprint 59/60.
- True structural causal inference (Sprint 55 reuses the existing intervention
  estimator at reduced confidence rather than fitting a new causal model).
