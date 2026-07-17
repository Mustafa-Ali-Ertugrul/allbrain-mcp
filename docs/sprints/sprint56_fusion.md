# Sprint 56 — Signal Fusion (Unified Decision Score) Layer

## Goal

Sprints 53–55 produced four independent signal channels — capability, learning,
dynamics, causal — each on its own scale. Sprint 56 **fuses** them into a single
unified decision score via calibrated normalization and adaptive weighting,
while detecting when channels are redundant (overlapping) so they don't
double-count. The system can now say:

- "Unified score for `codex` on `implementation` is 0.74 — capability 0.45,
  causal 0.20, learning 0.07, dynamics 0.02."
- "The `learning` and `dynamics` channels **overlap**; their weights were
  attenuated to avoid double-counting."
- "Channel `dynamics` had near-zero variance, so it was **soft-scaled** toward
  neutral instead of dominating."

## Architecture

```
CAPABILITY_MATCHED / AGENT_CAPABILITY_LEARNED /
AGENT_CAPABILITY_DRIFT_DETECTED / AGENT_COUNTERFACTUAL_RUN
  ↓  normalize_signal()  (z-score + sigmoid; soft-scale when variance < ε)
SIGNAL_CALIBRATED            (raw_mean, normalized_value, was_normalized)
  ↓  build_signal_vector() → SignalVector[capability, learning, dynamics, causal]
  ↓  compute_overlap_matrix() → calibrate_weights()
unified_decision_score()     (Σ vector[i] × weights[i], clipped [0,1])
  ↓
FUSION_COMPUTED              (unified score + per-channel weights + vector)
  ↓
FusionReducer → state["fusion"]
```

## Scope

### In

1. New module `src/allbrain/fusion/` (`fusion`, `calibration`, `events`,
   `model`, `manager`, `reducer`).
2. `unified_decision_score()` — pure, deterministic `f(v) = Σ v[i]·w[i]`,
   clipped to [0,1] (no state/IO).
3. `normalize_signal()` — z-score + sigmoid; soft-scaling when variance <
   `FUSION_MIN_VARIANCE_EPSILON` (0.01) to stop low-variance/high-bias channels
   dominating.
4. Adaptive weighting: `compute_overlap_matrix()` + `calibrate_weights()` plus
   overlap/violation detection; weights start uniform (0.25 each).
5. Models: `SignalVector`, `SignalWeights`.
6. Pipeline step (~`pipeline.py:2224`): projection only — no derived global
   state; emits `FUSION_COMPUTED` + `SIGNAL_CALIBRATED`.

### Out of scope (Sprint 57+)

- Environment-driven adaptation of the fusion (drift in the fused signal) —
  Sprint 57 dynamics/drift.
- Selecting *which mode* to run under the fused score — Sprint 58 meta-policy.
- Budgeting compute across channels by fused importance — Sprint 60 attention.
- Learned (gradient) weight optimization — Sprint 56 weighting is heuristic
  overlap-calibration, not trained.
