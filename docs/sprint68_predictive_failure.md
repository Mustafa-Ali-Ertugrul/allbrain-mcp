# Sprint 68 — Predictive Failure (Risk Drift Detection) Layer

## Goal

Sprints 64–67 *react* to failures. Sprint 68 flips the loop to be **proactive**:
it detects risk signals, computes a risk score, predicts likely failures before
they occur, plans mitigations, executes proactive actions, and — when it works —
records a failure *avoided*. It also tracks **risk drift** so it knows when the
risk landscape itself is shifting. The system can now say:

- "Risk signals `latency↑` + `error-rate↑` → risk 0.78 → **predict** failure
  `dep-timeout`."
- "Plan mitigation `pre-warm-cache`; execute proactively → failure **avoided**."
- "Baseline risk is **drifting** upward — recalibrate thresholds."

> Confirmed by git: commit *"Sprint 68: Predictive Failure with Risk Drift
> Detection"* maps to `src/allbrain/predictive_failure/`.

## Architecture

```
risk signals
  ↓
RiskEngine (_frequency_weight) / RiskDriftDetector
  → RISK_SIGNAL_DETECTED / RISK_COMPUTED
Predictor                → FAILURE_PREDICTED
MitigationPlanner        → MITIGATION_PLANNED
ProactiveExecutor        → RECOVERY_EXECUTED
                           FAILURE_AVOIDED
  ↓
PredictiveFailureReducer → state["predictive_failure"]
```

## Scope

### In

1. New module `src/allbrain/predictive_failure/` (`risk_engine`, `risk_drift`,
   `predictor`, `mitigation_planner`, `proactive_executor`, `events`, `model`,
   `manager`, `reducer`).
2. `RiskEngine` — compute risk from detected signals with frequency weighting.
3. `RiskDriftDetector` — detect drift in the risk distribution over time.
4. `Predictor` — predict likely failures from current risk.
5. `MitigationPlanner` / `ProactiveExecutor` — plan and execute proactive
   mitigations before failure occurs.
6. Models: `RiskSignal`, `FailurePrediction`, `MitigationPlan`,
   `ProactiveAction`.
7. Events: `RISK_SIGNAL_DETECTED`, `RISK_COMPUTED`, `FAILURE_PREDICTED`,
   `MITIGATION_PLANNED`, `RECOVERY_EXECUTED`, `FAILURE_AVOIDED`.

### Out of scope (Sprint 69)

- Learning which mitigations actually pay off and evolving the policy that
  selects them — Sprint 69.
- Closing the loop from `FAILURE_AVOIDED` back into strategy weights — Sprint 69
  mitigation learning.
