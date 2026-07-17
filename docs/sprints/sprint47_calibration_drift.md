# Sprint 47 — Calibration & Belief Drift

## Goal

Sprint 47 makes the system's trust accuracy measurable and its belief changes explainable. After this sprint the system can finally say:

- "My current trust score is X, but the historical accuracy of my trust predictions is Y, so my *calibrated* trust is X × (1 − Y)."
- "My belief shifted from 0.5 to 0.8 (magnitude 0.3) because of a `trust_shift`."

The Sprint 46 chain

```
Belief → Contradiction → Revision → Uncertainty → Trust
```

is extended (read-only, no recompute) with two display layers:

```
Trust → CALIBRATION_UPDATED  → Revision (calibrated_trust)
      ↘
       BELIEF_REVISED → BELIEF_DRIFT_DETECTED  → Revision (drift_count)
```

## Architecture

```
Events
  ↓
Evidence (emitted, EVIDENCE_RECORDED)
  ↓
Belief
  ↓
Contradiction
  ↓
Uncertainty
  ↓
Revision (× trust_score)         (Sprint 46, unchanged)
  ↓
BELIEF_DRIFT_DETECTED            (Sprint 47, new — emitted by _drift_step)
  ↓
CALIBRATION_UPDATED              (Sprint 47, new — emitted by _calibration_step)
  ↓
Snapshot (revision.{calibrated_trust, calibration_error, drift_count})
```

## Scope

### In

1. New module `src/allbrain/calibration/` (6 files: `__init__`, `model`, `estimator`, `events`, `reducer`, `manager`)
2. New module `src/allbrain/drift/` (3 files: `__init__`, `detector`, `events`)
3. Two new event types: `CALIBRATION_UPDATED`, `BELIEF_DRIFT_DETECTED`
4. New pipeline steps: `_calibration_step` + `_drift_step` (off-by-default flags)
5. Revision integration (Yol B display-only): `RevisionState` gains 3 fields, `confidence` is **unchanged**
6. Replay binding (`CalibrationReducer` + `state["drift"]` projection in `EventReplayEngine`)
7. 23 tests across 5 files + quality gate

### Out of scope (Sprint 48+)

- Per-agent calibration policies
- Bayesian calibration updates
- Drift reasons beyond the four `Final[frozenset]` values
- Auto-reverting belief revisions based on drift magnitude
- `enable_calibration=True` / `enable_drift=True` as default (recommended: keep off until Sprint 49–50)

---

## Resolved design decisions (Yol B display-only)

| Question | Decision |
|---|---|
| `revise()` signature | UNCHANGED — 4 args (Sprint 44 contract preserved) |
| `confidence` value | UNCHANGED — still `revise(...) × trust_score` (Sprint 46) |
| `calibrated_trust` formula | `trust_score × (1 - calibration_error)`, hard-clamped `[0, 1]` |
| `calibration_error` default | `0.0` when no `CALIBRATION_UPDATED` events (Yol B: no data = no penalty) |
| `drift_count` default | `0` when no `BELIEF_DRIFT_DETECTED` events |
| Drift threshold | `0.10` (below this, no event emitted) |
| Drift trigger | Revision step only (`_drift_step` is the single write-path) |
| Drift reasons | `Final[frozenset]`: `new_evidence`, `trust_shift`, `contradiction_resolution`, `uncertainty_change` |
| Pipeline default flags | `enable_calibration=False`, `enable_drift=False` (keep off until Sprint 49–50) |
| `calibrated_trust` clamp | **Mandatory** `max(0, min(1, value))` even for pathological inputs |
| Event source | Event log only (no recompute branch in revision layer) |

---

## Module changes

### `src/allbrain/calibration/`

**`model.py`** — `CalibrationState` frozen dataclass:
```python
@dataclass(frozen=True)
class CalibrationState:
    context_key: str
    sample_count: int
    mean_confidence: float
    accuracy: float
    calibration_error: float
    analysis_id: str
    template_version: int = 1
```

**`estimator.py`** — Pure functions:
```python
CALIBRATION_TEMPLATE_VERSION = 1

def _stable_calibration_id(context_key, event_ids) -> str:
    """sha256("|".join(sorted(...)))[:12], prefix 'calibration-'"""

def squared_error(confidence, outcome) -> float:
    """(confidence - (1.0 if outcome else 0.0))**2"""

def mean_calibration_error(samples) -> float:
    """mean of squared_error; 0.0 if empty (Yol B default)"""

def mean_confidence(samples) -> float: ...
def accuracy(samples) -> float: ...

def calibrated_trust(trust_score, calibration_error) -> float:
    """trust × (1 - error), hard-clamped [0, 1]"""
```

**`events.py`** — Payload helpers (mirrors evidence/trust event shape):
```python
REQUIRED_KEYS = frozenset({"context_key", "predicted_confidence", "actual_outcome"})
def validate_payload(payload) -> None: ...
def make_payload(*, context_key, predicted_confidence, actual_outcome, template_version=1) -> dict: ...
```

**`reducer.py`** — `CalibrationReducer`:
- Idempotent via `_seen_ids`
- `CALIBRATION_UPDATED`: append `(predicted, outcome)` to per-context list
- All other event types: no-op (unknown-event tolerance)
- `snapshot()`: same formula the manager uses

**`manager.py`** — `CalibrationManager.query`:
- `canonical_event_sort(events)`
- Builds `(predicted, outcome)` list from `CALIBRATION_UPDATED` matching `context_key`
- No recompute (Zorunlu)

### `src/allbrain/drift/`

**`detector.py`** — Pure drift detection:
```python
DRIFT_THRESHOLD: float = 0.10
DRIFT_TEMPLATE_VERSION: int = 1

REASONS: Final[frozenset[str]] = frozenset({
    "new_evidence",
    "trust_shift",
    "contradiction_resolution",
    "uncertainty_change",
})
# Future reasons may be added without breaking old logs.

@dataclass(frozen=True)
class DriftSample: ...

def detect_drift(belief_before, belief_after, *, context_key, reason) -> DriftSample | None:
    """Return None if |delta| < DRIFT_THRESHOLD."""
```

**`events.py`** — Payload helpers with magnitude validation:
```python
REQUIRED_KEYS = frozenset({"context_key", "belief_before", "belief_after", "magnitude", "reason"})

def validate_payload(payload) -> None:
    # Re-computes magnitude from belief_before/after; rejects mismatches
    ...
```

### `src/allbrain/events/schemas.py`
Added: `CALIBRATION_UPDATED = "calibration_updated"`, `BELIEF_DRIFT_DETECTED = "belief_drift_detected"` (EventType + SemanticEventType).

### `src/allbrain/revision/state.py`
Added 3 fields to `RevisionState` (with backward-compatible defaults):
```python
calibrated_trust: float = 1.0
calibration_error: float = 0.0
drift_count: int = 0
```

### `src/allbrain/revision/manager.py`
- New helper `_read_calibration_error(ordered, context_key) -> float`: scans event log for `CALIBRATION_UPDATED` matching context, computes mean squared error
- New helper `_read_drift_count(ordered, context_key) -> int`: counts `BELIEF_DRIFT_DETECTED` for context
- In `query()`: `calibrated_trust = trust × (1 - calibration_error)`
- `confidence` is unchanged (Yol B display-only)

### `src/allbrain/revision/reducer.py`
- New state fields: `_calibration_samples: dict[str, list[(float, bool)]]`, `_drift_count: dict[str, int]`
- New branches in `apply()` for `CALIBRATION_UPDATED` and `BELIEF_DRIFT_DETECTED`
- In `snapshot()`: same formula as the manager
- `_state_to_dict` includes the 3 new fields

### `src/allbrain/replay/event_replay_engine.py`
- Import `CalibrationReducer`
- State dict: `"calibration": {}`, `"drift": {}`
- Local var: `calibration_reducer = CalibrationReducer()` (added to `_apply` signature)
- `_apply`: `calibration_reducer.apply(event); state["calibration"] = calibration_reducer.all_snapshots()`
- `_apply`: tracks `BELIEF_DRIFT_DETECTED` events into `state["drift"][context_key]["count"]`
- `_copy_state`: includes `"calibration"` and `"drift"`

### `src/allbrain/runtime_core/pipeline.py`
- New flags: `enable_calibration`, `enable_drift` (off-by-default)
- New `_calibration_step`: emits `CALIBRATION_UPDATED` with `(belief.mean, last_outcome)` sample
- New `_drift_step`: emits `BELIEF_DRIFT_DETECTED` if `|new - old| >= 0.10`
- `_result()` signature gains `calibration` + `drift` keyword args
- Result dict gains `"calibration"` + `"drift"` keys

---

## Convergence invariant

`CalibrationManager.query(events, ctx=X) == CalibrationReducer.snapshot(ctx=X)` for ALL event logs.
`RevisionManager.query(events) == RevisionReducer.snapshot()` for ALL event logs (Sprint 47 fields included).

Locked by `test_calibration_reducer.py` (4 tests):
- manager == reducer no events
- manager == reducer with samples
- manager == reducer other-context ignored
- composition: trust + calibration = `0.8 × (1 - 0.25) = 0.6`

---

## Replay determinism

`EventReplayEngine().replay(events)["final_state"]["revision"]["default"]["calibrated_trust"]` MUST equal `RevisionReducer().snapshot().calibrated_trust` byte-for-byte.

Locked by `test_drift_replay.py::test_replay_calibrated_trust_matches_revision_snapshot`.

---

## Revision integration (Yol B display-only)

```
confidence       = max(0, min(1, revise(baseline, n, u, policy) × trust_score))   # Sprint 46, unchanged
calibration_error = mean((predicted_i - outcome_i)**2) over CALIBRATION_UPDATED    # Sprint 47
calibrated_trust  = max(0, min(1, trust_score × (1 - calibration_error)))         # Sprint 47
drift_count       = count of BELIEF_DRIFT_DETECTED for context                     # Sprint 47
```

**Yol B**: `calibration_error` and `calibrated_trust` are display-only. They NEVER modify the `confidence` field. The Sprint 46 contract (`revise() × trust_score`) is preserved exactly.

Verified by `test_calibration_does_not_change_confidence`:
- Add a `CALIBRATION_UPDATED` event to the log.
- `confidence` is byte-equal before and after.
- `calibrated_trust` and `calibration_error` change as expected.

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `calibration/estimator.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `calibration/reducer.py` | same |
| `calibration/manager.py` | same |
| `calibration/events.py` | same |
| `calibration/model.py` | same |
| `drift/detector.py` | same |
| `drift/events.py` | same |
| `revision/manager.py` | `CalibrationManager(`, `DriftSample(`, `detect_drift(` outside the helpers (live recompute forbidden) |

Quality gate (`tests/test_calibration_quality_gate.py`) reads each determinism-critical file and asserts none of the forbidden tokens appear.

---

## Tests (23 new in 5 files)

### `tests/test_calibration.py` (4 tests)
- `test_perfect_calibration` — (1.0, True) + (0.0, False) → error = 0
- `test_poor_calibration` — (0.9, False) + (0.1, True) → error = 0.81
- `test_empty_history` — no samples → error = 0, count = 0
- `test_bounds` — calibrated_trust is hard-clamped for all input ranges

### `tests/test_drift.py` (6 tests)
- `test_no_drift` — delta < threshold → None
- `test_positive_drift` — before=0.5, after=0.7 → magnitude=0.2
- `test_negative_drift` — before=0.7, after=0.5 → magnitude=0.2
- `test_threshold_filtering` — boundary cases (0.59, 0.61, exact 0.10)
- `test_reasons_set_is_final_and_closed` — `REASONS` is `Final[frozenset]` of 4 values
- `test_unknown_reason_raises` — closed-set enforcement

### `tests/test_calibration_reducer.py` (4 tests)
- `test_manager_equals_reducer_no_events`
- `test_manager_equals_reducer_with_samples` — 3 samples, exact agreement
- `test_manager_equals_reducer_other_context_ignored`
- `test_calibration_applied_after_trust_in_revision` — composition: `0.8 × (1 - 0.25) = 0.6`

### `tests/test_drift_replay.py` (5 tests)
- `test_drift_count_from_event_log` — 3 drift events → `drift_count == 3`
- `test_drift_count_zero_default` — no drift events → `drift_count == 0`
- `test_drift_replay_round_trip` — `state["drift"]` matches projection
- `test_replay_calibrated_trust_matches_revision_snapshot` — **strongest cross-check**
- `test_replay_calibration_round_trip` — `state["calibration"]` matches reducer

### `tests/test_calibration_quality_gate.py` (4 tests)
- `test_calibration_module_no_nondeterminism` — 5 files
- `test_drift_module_no_nondeterminism` — 2 files
- `test_revision_manager_reads_calibration_and_drift_from_event_log_only` — recompute branch forbidden
- `test_calibration_does_not_change_confidence` — **Yol B display-only contract**

### Existing tests — preserved
- All Sprint 46 tests pass unchanged
- `enable_calibration=False` + `enable_drift=False` preserves the Sprint 46 contract
- New fields have backward-compatible defaults (`calibrated_trust=1.0`, `calibration_error=0.0`, `drift_count=0`)

**Test count: 467 (Sprint 46) + 23 (new) = 490 (full regression passing)**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence | Medium | Both views consume the same event stream. Defaults (`calibration_error=0.0`) preserve Sprint 46 behavior. Tests lock convergence for full CALIBRATION+TRUST log. |
| Recompute branch drift | Medium | Quality gate forbids `CalibrationManager(`, `DriftSample(`, `detect_drift(` calls in `revision/manager.py` outside the helpers. |
| Determinism loss | Medium | Quality gate forbids `uuid7/datetime.now/random./time.time` in 5 calibration + 2 drift files. All formulas are pure math. |
| Drift event explosion | Low | `DRIFT_THRESHOLD = 0.10` filters out small changes. Most revision runs produce 0–1 drift events. |
| `calibrated_trust` unbounded | Low | **Mandatory** hard-clamp in `calibrated_trust()` function. Future models producing > 1.0 errors will be silently bounded. |
| Future reason migration | Low | `REASONS: Final[frozenset]` is closed-set on the write-path. New reasons are forward-compatible: new logs carry wider sets, old replays ignore new reasons losslessly. |

---

## Production impact

- `EventReplayEngine.replay()` now includes `state["calibration"]` and `state["drift"]` in `final_state`. Replay-derived state and live-derived state share the same event-sourcing semantics.
- `RevisionManager.query()` and `RevisionReducer.snapshot()` now expose `calibrated_trust`, `calibration_error`, `drift_count`. The `confidence` field is unchanged.
- The system can finally say "My trust is X but historically it's been off by Y, so my calibrated trust is X × (1 − Y)" and "My belief shifted from 0.5 to 0.8 because of trust_shift".

---

## Out-of-scope reminders (Sprint 48+)

- ❌ `enable_calibration=True` / `enable_drift=True` as default (recommended: keep off until Sprint 49–50 after replay stability is monitored)
- ❌ Per-agent calibration policies
- ❌ Bayesian calibration updates
- ❌ Auto-reverting belief revisions based on drift magnitude
- ❌ Drift reasons beyond the four `Final[frozenset]` values (extensible, but not now)
- ❌ Drift triggered from non-revision steps (currently only `_drift_step` is the single write-path)
