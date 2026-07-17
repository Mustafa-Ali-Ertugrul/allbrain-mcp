# Sprint 57 — Fused-Signal Drift Detection Layer

## Goal

Sprint 56 produced a unified, calibrated decision score. Sprint 57 watches that
fused score (and its input distribution) for **distribution drift** — the signal
that the environment has shifted out from under the system's learned weights. It
is a dedicated, lightweight drift detector distinct from the per-capability
`dynamics` drift of Sprint 54: this one operates on the *fused* signal stream.
The system can now say:

- "The fused decision distribution has **drifted** beyond threshold since the
  last baseline — the current weighting may be stale."
- "No drift: the recent samples are within tolerance of the reference window."

## Architecture

```
fused / signal samples (DriftSample stream)
  ↓
detect_drift()        (reference window vs. recent window comparison)
  ↓
validate_payload() / make_payload()
  ↓
*_DRIFT_DETECTED      (drift magnitude + level, threshold-gated)
  ↓
state["drift"]  (last-wins)
```

## Scope

### In

1. New module `src/allbrain/drift/` (`detector`, `events`).
2. `DriftSample` — typed sample record fed into the detector.
3. `detect_drift()` — windowed reference-vs-recent comparison producing a drift
   magnitude/level with a threshold gate.
4. Event validation/construction helpers (`validate_payload`, `make_payload`).
5. Replay binding via `state["drift"]`.

### Out of scope (Sprint 58+)

- Choosing a response *policy/mode* once drift is detected — Sprint 58 meta-policy.
- Re-weighting fusion in reaction to drift — handled by the adaptive fusion
  weighting (Sprint 56), not this detector.
- Forecasting future drift — Sprint 54 `dynamics.forecast` covers per-capability
  forecasting; fused-signal forecasting is out of scope here.
- Acting on drift (recovery / mitigation) — Sprint 64+ failure layers.
