# Sprint 44 — Belief Revision & Confidence Dynamics

## Goal

Teach the system to change its mind. Sprint 42 produced belief and Sprint 43 produced contradiction; Sprint 44 layers a revision layer on top that emits a `BELIEF_REVISED` event when belief is adjusted in response to contradiction pressure.

After Sprint 44 the system supports four new behaviors:

- **belief weakens** — `revise()` subtracts `contradiction_count * contradiction_penalty`
- **belief becomes uncertain** — `revise()` subtracts `uncertainty * uncertainty_penalty`
- **belief gets revised** — a `BELIEF_REVISED` event is emitted recording the new confidence
- **belief strengthens** — out of scope for Sprint 44 (no positive-evidence trigger yet)

## Architecture

```
Events
  ↓
Belief State (BELIEF_COMPUTED)
  ↓
Contradiction State (CONTRADICTION_DETECTED)
  ↓
Revision Layer (BELIEF_REVISED)  ← Sprint 44
  ↓
Revised Beliefs
```

## Scope

### In
1. New event: `EventType.BELIEF_REVISED` + `SemanticEventType` entry
2. New module `src/allbrain/revision/` (7 files)
3. Pipeline emit (`_revision_step`) with `enable_revision` flag (off by default)
4. Replay binding (`RevisionReducer` in `EventReplayEngine`)
5. 36 tests across 5 files + quality gate
6. Doc (`docs/sprint44_belief_revision.md`)

### Out of scope (Sprint 45+)
- `BELIEF_REVISION_REVERTED` (closed-lifecycle)
- Bayesian posterior update on revision
- Multi-source evidence fusion (only contradiction-driven for now)
- Per-agent / per-context-key policies (single global `RevisionPolicy`)
- Cascade revision (revision triggering revision)
- Real `UncertaintyManager.analyze()` integration (Sprint 44 defaults to `composite_uncertainty = 0.0`)
- Replay engine registry refactor (inline binding stays)

---

## Resolved design decisions

| Question | Decision |
|---|---|
| `revise()` formula | Linear: `new = confidence − n·p − u·up`, clamped to [0, 1] |
| Uncertainty source | Composite: `max(belief.variance, uncertainty.uncertainty)` — manager/reducer-derived, passed to `revise()` |
| Trailing window | CONTRADICTION_DETECTED **event count** (not payload-sum) |
| Baseline confidence | Last `BELIEF_REVISED` payload's `new_confidence`, else empty (no recompute from belief/uncertainty in Sprint 44) |
| `evidence_count` | Stored as historical record; NOT used by snapshot's `contradiction_count` |
| `reason` field | Hardcoded `"contradiction"` for Sprint 44 |
| Spec example `0.63` | Linear formula gives `0.355` — example was illustrative; tests assert `0.355` |

---

## Module layout — `src/allbrain/revision/`

```
revision/
├── __init__.py     # public re-exports
├── events.py       # payload validation, template_version, make_payload
├── policies.py     # RevisionPolicy (frozen dataclass) + REVISION_TEMPLATE_VERSION
├── state.py        # RevisionState (frozen dataclass)
├── estimator.py    # revise(), _stable_revision_id, composite_uncertainty
├── reducer.py      # RevisionReducer (mirrors Belief/Contradiction reducer)
└── manager.py      # RevisionManager.query() (mirrors Belief/Contradiction manager)
```

### `policies.py`
```python
@dataclass(frozen=True)
class RevisionPolicy:
    contradiction_penalty: float = 0.25
    evidence_bonus: float = 0.05
    uncertainty_penalty: float = 0.15

REVISION_TEMPLATE_VERSION = 1
```

### `estimator.py`
- `_stable_revision_id(context_key, evidence_event_ids)` = `sha256("|".join(sorted(evidence)))[:12]`, prefix `revision-`
- `revise(confidence, contradiction_count, uncertainty, policy)` = linear formula, clamped [0, 1]
- `composite_uncertainty(belief_variance, uncertainty)` = `max(variance, uncertainty)`

### `reducer.py`
- Idempotent via `_seen_ids` (mirrors belief/contradiction)
- Only consumes `BELIEF_REVISED` (authoritative overwrite) and `CONTRADICTION_DETECTED` (trailing counter increment)
- All other event types: no-op (unknown-event tolerance)
- `snapshot()` applies `revise(baseline, trailing_count, 0, policy)` where `baseline = payload['new_confidence']` and `trailing_count` is the count of CONTRADICTION_DETECTED events after the last BELIEF_REVISED
- `analysis_id = sha256(sorted(_seen_ids))` — single source of truth with the manager

### `manager.py`
- `canonical_event_sort(events)` for order-independence
- Finds LAST `BELIEF_REVISED` checkpoint for the context_key
- baseline = `payload['new_confidence']`
- Counts CONTRADICTION_DETECTED events AFTER the checkpoint
- Applies `revise()` with the same formula as the reducer
- `composite_uncertainty = 0.0` (Sprint 44 default; Sprint 45+ wires `UncertaintyManager.analyze()`)

### `events.py`
- `REVISION_REASON_CONTRADICTION = "contradiction"`
- `validate_payload(payload)` — required keys, type/range checks
- `make_payload(*, context_key, old_confidence, new_confidence, reason, evidence_count)` — full builder with `template_version`

---

## Convergence invariant

`RevisionManager.query(events, ctx=X) == RevisionReducer.snapshot(ctx=X)` for ALL event logs.

Both views consume the same event stream and apply the same `revise()` formula to the same baseline + trailing count. Locked by:

- `test_convergence_with_mixed_log_and_trailing_contradictions` — mixed log with BELIEF_REVISED + 2 trailing CONTRADICTION_DETECTED events
- `test_manager_equals_reducer_after_replay_round_trip` — exact dict equality through the replay engine

The reducer's order-dependence on `apply()` is intentional: it mirrors `BeliefReducer.apply()` which assumes canonical-ordered input. The replay engine's `_ordered()` guarantees canonical order via `canonical_event_sort`. The manager uses `canonical_event_sort` internally, so it's order-independent at the API level.

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `revision/estimator.py` | `uuid7`, `datetime.now`, `random.`, set/dict iteration order |
| `revision/reducer.py` | same |
| `revision/reducer.py` | same |
| `belief/{estimator,reducer,manager}.py` | (Sprint 42 contract — re-confirmed) |

Quality gate (`test_revision_quality_gate_no_uuid7_or_now_or_random_in_determinism_path`) reads each determinism-critical file and asserts none of the forbidden tokens appear.

---

## Pipeline emit — `_revision_step`

```python
def _revision_step(bus, belief_state, contradiction_payload, uncertainty_payload, caused_by):
    old_confidence = float(getattr(belief_state, "mean", 0.0))
    contradiction_count = len(contradiction_payload.get("contradictions", [])) if contradiction_payload else 0
    uncertainty = float(uncertainty_payload.get("uncertainty", 0.0)) if uncertainty_payload else 0.0
    new_confidence = revise(old_confidence, contradiction_count, uncertainty, RevisionPolicy())
    payload = make_payload(context_key="default", old_confidence, new_confidence, "contradiction", contradiction_count)
    return bus.publish(type=EventType.BELIEF_REVISED.value, payload=payload, caused_by=caused_by, impact_score=delta)
```

Off by default (`enable_revision=False`). Three `_result` call sites have been updated to propagate `revision=revision_payload`; the two BLOCKED sites default to `None` via the keyword-only signature.

---

## Tests (36 new in 5 files)

### `tests/test_revision_estimator.py` (14 tests)
- Linear formula, monotonicity, floor/ceiling clamp, composite_uncertainty, policy validation

### `tests/test_revision_determinism.py` (7 tests)
- `_stable_revision_id` order-independence, context distinction, prefix
- Reducer determinism for canonical-ordered input
- Manager order-independence
- Quality gate (uuid7 / datetime.now / random.)

### `tests/test_revision_convergence.py` (5 tests)
- No-checkpoint empty, with-checkpoint full, mixed log + trailing, replay round-trip (exact dict equality), quality gate

### `tests/test_revision_checkpoint.py` (5 tests)
- Last payload wins, no-checkpoint empty, trailing count = event count (not payload-sum), intent events don't affect revision, baseline = payload's new_confidence

### `tests/test_revision_policy.py` (5 tests)
- Default values, custom policy flows through manager/reducer, validation, immutability

### Existing tests — preserved
- `test_belief_convergence.py` (5) — untouched
- `test_belief_updater.py` (5) — untouched
- `test_contradiction_convergence.py` (13) — untouched
- `test_intent.py` (12) — untouched
- All 378 pre-Sprint-44 tests still pass

**Test count: 378 → 414 (full suite passing in 374s).**

---

## Production impact

- `query_belief`-style MCP tools can now also expose revision state via `EventReplayEngine.replay()` or `RevisionManager.query()` — both guaranteed to return the same snapshot for the same event log.
- The pipeline emits `BELIEF_REVISED` snapshots when `enable_revision=True`. The replay-derived state and live-derived state now share the same event-sourcing semantics.
- The revision layer reads `belief_state.mean`, `contradiction_payload.contradictions`, and `uncertainty_payload.uncertainty` — all three layers are now wired together in a single pipeline step.

---

## Out-of-scope reminders (Sprint 45+)

- `BELIEF_REVISION_REVERTED` (closed-lifecycle event)
- Bayesian posterior update on revision
- Multi-source evidence fusion
- Per-agent / per-context-key policies
- Cascade revision (revision triggering revision)
- Real `UncertaintyManager.analyze()` integration in `_revision_step`
- Replay engine registry refactor