# Sprint 45 — Uncertainty Integration & Epistemic Confidence

## Goal

Replace the hardcoded `composite_uncertainty = 0.0` in the revision layer with a real value sourced from the event log. After Sprint 45, the revision layer consumes `UNCERTAINTY_COMPUTED` events (last-wins authoritative) and uses them in `revise()`. The system can finally say "I believe this, but the evidence is quite uncertain" — not just "I believe this."

## Architecture

```
Events
  ↓
Belief State (BELIEF_COMPUTED)
  ↓
Contradiction State (CONTRADICTION_DETECTED)
  ↓
Uncertainty State (UNCERTAINTY_COMPUTED)  ← Sprint 45
  ↓
Revision Layer (BELIEF_REVISED)
```

## Scope

### In
1. New event: `EventType.UNCERTAINTY_COMPUTED` + `SemanticEventType` entry (coexists with existing `UNCERTAINTY_ESTIMATED`)
2. New pipeline step: `_uncertainty_computed_step` (off-by-default `enable_uncertainty_computed` flag), emits `UNCERTAINTY_COMPUTED` BEFORE `_revision_step`
3. New estimator function: `composite_uncertainty(variance, evidence_count, contradiction_count) -> variance + n/e` in `src/allbrain/uncertainty/estimator.py`
4. Revision reducer/manager consume `UNCERTAINTY_COMPUTED` in the trailing slice (last-wins authoritative)
5. Tests — 4 new test files (23 tests) + extended quality gate; removed 2 Sprint 44 tests that referenced the old 2-arg `composite_uncertainty`
6. Doc — `docs/sprint45_uncertainty_integration.md`

### Out of scope (Sprint 46+)
- Real `UncertaintyManager.analyze()` integration (already deferred from Sprint 44)
- Per-context uncertainty policies
- Uncertainty-decay over time
- Replacing `UNCERTAINTY_ESTIMATED` (it stays; revision layer ignores it)
- Bayesian posterior updates on uncertainty

---

## Resolved design decisions

| Question | Decision |
|---|---|
| `UNCERTAINTY_COMPUTED` coexistence | New event alongside existing `UNCERTAINTY_ESTIMATED` (Path A) |
| `composite_uncertainty` formula | `variance + contradiction_count / evidence_count` (linear; example 0.31 in spec ≈ 0.30) |
| Function location | `src/allbrain/uncertainty/estimator.py` — Sprint 44's 2-arg version **removed** |
| `evidence_count` source | Total events in the log (from `repository.list_events` count) |
| `confidence_interval` | `uncertainty * 0.5` (deterministic, simple) |
| Pipeline emit timing | Same run, BEFORE `_revision_step` (reads `uncertainty_computed_payload`) |
| `_revision_step` input | `uncertainty_computed_payload` (new variable) — Sprint 44's `uncertainty_payload` was reading a dict (the bug) |

---

## Module changes

### `src/allbrain/events/schemas.py`
- New `UNCERTAINTY_COMPUTED = "uncertainty_computed"` in `EventType` (after `BELIEF_REVISED`)
- New `EventType.UNCERTAINTY_COMPUTED` in `SemanticEventType` set

### `src/allbrain/uncertainty/estimator.py` — new 3-arg `composite_uncertainty`
```python
def composite_uncertainty(variance, evidence_count, contradiction_count) -> float:
    """variance + contradiction_count / evidence_count, clamped to [0, 1]."""
    if evidence_count <= 0:
        return max(0.0, min(1.0, float(variance)))
    raw = float(variance) + float(contradiction_count) / float(evidence_count)
    return max(0.0, min(1.0, raw))
```

Spec example: variance=0.20, evidence=20, contradictions=2 → 0.20 + 0.10 = **0.30** (not 0.31; example was approximate — user accepted in clarification).

### `src/allbrain/uncertainty/events.py` (NEW)
- `UNCERTAINTY_COMPUTED_TEMPLATE_VERSION = 1` (separate from `UNCERTAINTY_TEMPLATE_VERSION` in `models.py` to avoid shadowing)
- `validate_payload(payload)` — required keys, type/range checks (uncertainty and confidence_interval in [0, 1], evidence_count >= 0)
- `make_payload(*, context_key, uncertainty, confidence_interval, evidence_count)` — full builder with `template_version`

### `src/allbrain/uncertainty/__init__.py`
Re-exports: `composite_uncertainty`, `validate_payload`, `make_payload`, `UNCERTAINTY_COMPUTED_TEMPLATE_VERSION`. Note: `UNCERTAINTY_TEMPLATE_VERSION` (from `models.py`) and `UNCERTAINTY_COMPUTED_TEMPLATE_VERSION` (from `events.py`) coexist — both currently `1` but semantically distinct.

### `src/allbrain/revision/estimator.py` — REMOVE 2-arg `composite_uncertainty`
Sprint 44's `composite_uncertainty(belief_variance, uncertainty) -> max(...)` is removed. The function lives in the uncertainty module now (3-arg version).

### `src/allbrain/revision/__init__.py`
- Removed `composite_uncertainty` from `__all__`
- Added `revise` import (it was missing — regression test caught this)

### `src/allbrain/revision/reducer.py` — process UNCERTAINTY_COMPUTED
- New state field: `_last_uncertainty: dict[str, float] = {}` (per-context)
- New branch in `apply()` for `UNCERTAINTY_COMPUTED`: validates payload, stores `payload["uncertainty"]` in `_last_uncertainty[context_key]` (last-wins, but tracking per-context)
- `snapshot()`: `last_uncertainty = self._last_uncertainty.get(context_key, 0.0)` then `revise(baseline, trailing_count, last_uncertainty, policy)`

### `src/allbrain/revision/manager.py` — read last UNCERTAINTY_COMPUTED
After finding the last `BELIEF_REVISED`, iterate the trailing slice ONCE and accumulate both `contradiction_count` and `last_uncertainty`:
- Count `CONTRADICTION_DETECTED` events
- For `UNCERTAINTY_COMPUTED` events (matching `context_key`): take the last one's `payload.uncertainty` scalar

Then `revise(baseline, contradiction_count, last_uncertainty, self._policy)`. **No recompute branch** (Zorunlu: if no `UNCERTAINTY_COMPUTED` in log, use 0.0, NOT a derivation from belief.variance or contradiction_count).

### `src/allbrain/runtime_core/pipeline.py` — new `_uncertainty_computed_step`
```python
def _uncertainty_computed_step(self, bus, context, project_path, belief_state, contradiction_payload, caused_by, limit):
    variance = float(getattr(belief_state, "variance", 0.0))
    contradiction_count = len(contradiction_payload.get("contradictions", [])) if contradiction_payload else 0
    evidence_count = len(context.repository.list_events(project_path=resolved, limit=limit))
    uncertainty = composite_uncertainty(variance, evidence_count, contradiction_count)
    confidence_interval = uncertainty * 0.5
    payload = make_payload(context_key="default", uncertainty, confidence_interval, evidence_count)
    event = bus.publish(type=EventType.UNCERTAINTY_COMPUTED.value, payload, caused_by, impact_score=uncertainty)
    return summary, event.id, [event]
```

In `run()`:
- New `enable_uncertainty_computed: bool = False` flag
- `uncertainty_computed_payload` orchestrator variable
- Step order: contradiction → uncertainty_computed → revision (revision reads uncertainty)
- `_revision_step` signature changed: `uncertainty_computed_payload` (not `uncertainty_payload`)

### Bug fix
Sprint 44's `_revision_step` was reading `uncertainty_payload["uncertainty"]` expecting a scalar, but `_uncertainty_step`'s payload stores a dict (`UncertaintyEstimate` object) at that key. The `isinstance(raw, (int, float))` check silently failed → `composite_uncertainty = 0.0` was a silent bug, not a design choice. Sprint 45 fixes this by introducing `UNCERTAINTY_COMPUTED` with a clean scalar payload.

---

## Convergence invariant

`RevisionManager.query(events, ctx=X) == RevisionReducer.snapshot(ctx=X)` for ALL event logs.

Both views consume the same event stream and apply the same `revise()` formula to the same `(baseline, contradiction_count, last_uncertainty)`. Locked by:

- `test_revision_uncertainty_convergence.py` — manager == reducer on logs with UNCERTAINTY_COMPUTED
- `test_trailing_uncertainty.py` — checkpoint + UNCERTAINTY_COMPUTED + CONTRADICTION_DETECTED in various orderings
- `test_uncertainty_authoritative.py` — last UNCERTAINTY_COMPUTED wins (override semantic)

**Zorunlu constraint**: "if uncertainty missing: recompute() yasaktır". Both views default to `0.0` if no `UNCERTAINTY_COMPUTED` is in the log. No derivation from `belief.variance` or `contradiction_count` happens in the manager/reducer. Test `test_uncertainty_payload_is_read_directly` proves the manager reads the payload, not recomputes — the test uses `uncertainty=0.99` (not what `composite_uncertainty` would produce) and asserts the manager uses 0.99.

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `uncertainty/estimator.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `revision/estimator.py` | same |
| `revision/reducer.py` | same |
| `revision/manager.py` | same |

`composite_uncertainty(variance, evidence_count, contradiction_count)` is a pure function: same inputs → same output. Quality gate (in `test_revision_convergence.py`) reads each determinism-critical file and asserts none of the four forbidden tokens appear.

---

## Tests (4 new files, 23 new tests, -2 Sprint 44 tests, +1 quality gate extension)

### `tests/test_uncertainty_estimator.py` (10 tests)
- Linear formula, ceiling clamp, floor clamp, zero-evidence returns variance, monotonic in contradictions, monotonic decreasing in evidence, make_payload, validation rejection, validate_payload accepts valid, template_version constant

### `tests/test_revision_uncertainty_convergence.py` (4 tests)
- manager == reducer with uncertainty, no uncertainty defaults to 0.0, replay round-trip exact equality, uncertainty in payload changes confidence

### `tests/test_trailing_uncertainty.py` (4 tests)
- Uncertainty between checkpoint and contradiction, contradiction between checkpoint and uncertainty, multiple uncertainty events last-wins, mixed trailing events

### `tests/test_uncertainty_authoritative.py` (5 tests)
- Last uncertainty overrides earlier, payload is read directly (not recomputed), other-context isolation, invalid payload ignored, validate_payload accepts valid

### `tests/test_revision_convergence.py` (extended)
- `test_revision_quality_gate_no_uuid7_or_now_or_random_in_determinism_path` extended to forbid `time.time` and to cover `uncertainty/estimator.py`

### Tests REMOVED (Sprint 44 cleanup)
- `tests/test_revision_estimator.py`: `test_composite_uncertainty_takes_max`, `test_composite_uncertainty_handles_none_and_zero` — referenced the old 2-arg `composite_uncertainty` that no longer exists

### Existing tests — preserved
- All other Sprint 42-44 tests pass unchanged (412 of them)
- The `_revision_step` signature change is internal — no external API user is affected

**Test count: 414 (Sprint 44) - 2 (removed) + 23 (new) = 435**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence (Sprint 42/43/44 pattern) | Medium | Both views consume the same event stream. Last-wins is enforced by both. Test `test_manager_equals_reducer_with_uncertainty` locks convergence. |
| Determinism loss (uuid7/now/random/time.time creep) | Medium | Quality gate covers all 4 forbidden tokens. `composite_uncertainty` is a pure function. |
| `_revision_step` input break (now reads `uncertainty_computed_payload`) | Medium | Documented. Old `uncertainty_payload` was reading a dict (silent bug). New variable has a clean scalar. No external API user is affected (this is an internal method). |
| Spec example mismatch (0.30 vs 0.31) | Low | Documented as approximate. User accepted in clarification. |
| `enable_uncertainty_computed` interaction with existing `enable_uncertainty` | Low | Independent flags. `enable_uncertainty` controls the existing `UNCERTAINTY_ESTIMATED`. `enable_uncertainty_computed` controls the new `UNCERTAINTY_COMPUTED`. Both can be on simultaneously. |

---

## Production impact

- The revision layer now consumes a real uncertainty value from the event log. `BELIEF_REVISED` payloads record the `old_confidence`, `new_confidence`, `reason`, and `evidence_count` — the revision's `revise()` call is informed by the most recent `UNCERTAINTY_COMPUTED` value, not a hardcoded 0.0.
- `query_belief`/`query_contradiction`/`query_revision` MCP tools can now compose: read belief.mean, contradiction.count, last UNCERTAINTY_COMPUTED.uncertainty, and the system can finally say "I believe this with confidence X, but the evidence is Y uncertain."
- The `composite_uncertainty` function is exposed via `from allbrain.uncertainty import composite_uncertainty` for any other module that wants to compute a deterministic uncertainty composite.

---

## Out-of-scope reminders (Sprint 46+)

- ❌ `UncertaintyManager.analyze()` integration in `_revision_step` (still deferred)
- ❌ Replacing `UNCERTAINTY_ESTIMATED` (it stays for the existing uncertainty manager)
- ❌ Per-context uncertainty policies
- ❌ Uncertainty-decay over time
- ❌ Bayesian posterior updates on uncertainty
- ❌ Real epistemic-uncertainty separation (only scalar uncertainty for Sprint 45)