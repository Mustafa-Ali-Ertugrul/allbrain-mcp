# Sprint 48 — Agent Reputation Layer

## Goal

Sprint 48 makes agent reliability a first-class entity and extends the revision
layer's trust surface from "evidence/trust per context" (Sprint 46) to "source
reliability per agent". After this sprint the system can finally say:

- "Agent `codex` has completed 30 tasks with a 0.82 success rate and a 0.90
  confidence mean, so its reputation score is 0.78."
- "I believe this (confidence X), the evidence's trustworthiness is Y (Sprint
  46), and the executing agent's historical reliability is 0.78 (Sprint 48)."

The Sprint 46 chain

```
Belief → Contradiction → Revision → Uncertainty → Trust
```

is extended (read-only, no recompute) with a per-agent reputation signal that
the revision layer surfaces as `RevisionState.agent_reputation`:

```
AGENT_REPUTATION_UPDATED → Revision (agent_reputation, last-wins, default 1.0)
```

Reputation is **observation-only metadata**: it is recorded from the pipeline
run outcome and the scheduler assignment, and it is never recomputed from task
outcomes inside the replay path. The Sprint 46 `confidence` contract is
preserved exactly.

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
Revision (× trust_score)                       (Sprint 46, unchanged)
  ↓
AGENT_REPUTATION_UPDATED                       (Sprint 48, new — emitted by _reputation_step)
  ↓
Revision (agent_reputation)                    (Sprint 48, last-wins, default 1.0)
  ↓
Snapshot (revision.agent_reputation)
```

## Scope

### In

1. New module `src/allbrain/reputation/` (6 files: `__init__`, `model`, `estimator`, `events`, `reducer`, `manager`)
2. One new event type: `AGENT_REPUTATION_UPDATED`
3. New pipeline step: `_reputation_step` (off-by-default flag)
4. Revision integration (Yol B display-only): `RevisionState` gains the `agent_reputation` field, `confidence` is **unchanged**
5. Replay binding (`ReputationReducer` + `state["reputation"]` projection in `EventReplayEngine`)
6. 36 tests across 4 files + quality gate

### Out of scope (Sprint 49+)

- Multi-agent reputation fusion (one reputation score per agent, no cross-agent blend)
- Reputation-weighted scheduling override (reputation is metadata; the scheduler is untouched)
- Execution-driven reputation updates (Sprint 48: `duration_ms=0`, `retry_count=0` placeholders — real execution telemetry is Sprint 50)
- Bayesian posterior updates on reputation
- Per-task-type reputation (reputation is per-agent, not per `(agent, task_type)` — that arrives in Sprint 52/53 with capabilities/learning)

---

## Resolved design decisions (Yol B display-only)

| Question | Decision |
|---|---|
| `revise()` signature | UNCHANGED — 4 args (Sprint 44 contract preserved) |
| `confidence` value | UNCHANGED — still `revise(...) × trust_score` (Sprint 46) |
| `agent_reputation` formula | `success_rate × 0.5 + mean_confidence × 0.3 + consistency × 0.2`, hard-clamped `[0, 1]` |
| `consistency` formula | `1 − min(1, mean_retry / REPUTATION_MAX_RETRY)`; `1.0` when empty (no data = no penalty) |
| `agent_reputation` default | `1.0` when no `AGENT_REPUTATION_UPDATED` events (Yol B: no data = full trust, never `0.0`) |
| `reputation_score` empty default | `0.0` for the reducer/manager (zero samples = zero score); the *revision* default is `1.0` (no event read = assume full trust) |
| Reputation scope | Per-agent (`agent_id`), not per-context — no `context_key` filter |
| Last-wins vs aggregate | Revision reads last `reputation_score` (last-wins); reducer/manager aggregate ALL samples |
| `duration_ms` / `retry_count` source | Pipeline stamps `0.0` placeholder for both (execution telemetry is Sprint 50) |
| Pipeline default flag | `enable_reputation=False` (keep off until downstream consumers stabilize) |
| Event source | Event log only (no recompute branch in revision layer) |

---

## Module changes

### `src/allbrain/reputation/`

**`model.py`** — `ReputationState` frozen dataclass:
```python
REPUTATION_TEMPLATE_VERSION = 1

@dataclass(frozen=True)
class ReputationState:
    agent_id: str
    task_count: int
    success_rate: float
    mean_confidence: float
    mean_duration_ms: float
    mean_retry_count: float
    reputation_score: float
    analysis_id: str
    template_version: int = REPUTATION_TEMPLATE_VERSION
```

**`estimator.py`** — Pure functions (no I/O, no time, no randomness):
```python
REPUTATION_TEMPLATE_VERSION = 1
REPUTATION_MAX_RETRY = 5.0

def _stable_reputation_id(agent_id, event_ids) -> str:
    """sha256(f"{agent_id}:{'|'.join(sorted(event_ids))}")[:12], prefix 'reputation-'"""

def success_rate(samples) -> float:
    """fraction where success == True. 0.0 for empty list."""

def mean_confidence(samples) -> float:
    """mean of confidence. 0.0 for empty list."""

def mean_duration(samples) -> float:
    """mean of duration_ms. 0.0 for empty list."""

def mean_retry(samples) -> float:
    """mean of retry_count. 0.0 for empty list."""

def consistency(samples) -> float:
    """1 − min(1, mean_retry / REPUTATION_MAX_RETRY). 1.0 for empty list."""

def reputation_score(samples) -> float:
    """success_rate×0.5 + mean_confidence×0.3 + consistency×0.2, clamped [0,1].
       0.0 for empty list."""
```

A sample is the tuple `(success: bool, confidence: float, duration_ms: float, retry_count: float)`.

**`events.py`** — Payload helpers:
```python
REQUIRED_KEYS = frozenset({"agent_id", "task_id", "success", "confidence",
                           "duration_ms", "retry_count"})

def validate_payload(payload) -> None:
    """REQUIRED_KEYS subset check + per-field type/range validation
    (agent_id/task_id non-empty str, success bool, confidence in [0,1],
     duration_ms/retry_count >= 0)."""

def make_payload(*, agent_id, task_id, success, confidence,
                 duration_ms, retry_count, reputation_score,
                 analysis_id, template_version=1) -> dict:
    """Coerce types, validate, return dict."""
```

**`reducer.py`** — `ReputationReducer`:
- Idempotent via `_seen_ids`
- `AGENT_REPUTATION_UPDATED`: append `(success, confidence, duration_ms, retry_count)` to per-agent list (validated)
- All other event types: no-op (unknown-event tolerance)
- Invalid payloads: no-op (swallowed)
- `snapshot(agent_id)`: same formula the manager uses
- `all_snapshots()`: every known agent → state dict
- `known_agent_ids()`: set of agent ids seen

**`manager.py`** — `ReputationManager`:
- `query(events, *, agent_id="default", analysis_id=None)`: `canonical_event_sort(events)`, collect samples from `AGENT_REPUTATION_UPDATED` matching `agent_id`, compute state. No recompute (Zorunlu)
- `known_agent_ids(events)`: agents observed in the log

### `src/allbrain/events/schemas.py`
Added: `AGENT_REPUTATION_UPDATED = "agent_reputation_updated"` (EventType + SemanticEventType).

### `src/allbrain/revision/state.py`
Added `agent_reputation: float = 1.0` field to `RevisionState` (backward-compatible default).

### `src/allbrain/revision/manager.py`
- New helper `_read_agent_reputation(ordered) -> float`: scans for the last `AGENT_REPUTATION_UPDATED` `reputation_score`, defaults to `1.0`. Last-wins (no context filter — reputation is per-agent)
- `confidence` is unchanged (Yol B display-only)
- Quality gate forbids instantiating `ReputationManager(` / `ReputationReducer(` outside the helper

### `src/allbrain/replay/event_replay_engine.py`
- Import `ReputationReducer`
- State dict: `"reputation": {}`
- `_apply`: `reputation_reducer.apply(event); state["reputation"] = reputation_reducer.all_snapshots()`
- `_copy_state`: includes `"reputation"`

### `src/allbrain/runtime_core/pipeline.py`
- New flag: `enable_reputation` (off-by-default)
- New `_reputation_step`: takes the scheduler assignment's `agent_id`, the pipeline feedback `actual_success`, and `belief_state.mean` (confidence). Reads prior `AGENT_REPUTATION_UPDATED` events for the agent, appends the new `(success, confidence, 0.0, 0.0)` sample, recomputes the score, emits `AGENT_REPUTATION_UPDATED` with `impact_score = abs(score − 0.5)`
- `_result()` signature gains `reputation` keyword arg
- Result dict gains `"reputation"` key

---

## Convergence invariant

`ReputationManager.query(events, agent_id=X) == ReputationReducer.snapshot(agent_id=X)` for ALL event logs.

Locked by `test_reputation_reducer.py`:
- manager == reducer no events
- manager == reducer with samples
- manager == reducer other-agent ignored
- last-wins aggregation matches reducer sample list

---

## Replay determinism

`EventReplayEngine().replay(events)["final_state"]["reputation"][X]["reputation_score"]` MUST equal `ReputationReducer().snapshot(agent_id=X).reputation_score` byte-for-byte.

Locked by `test_reputation_replay.py`.

---

## Revision integration (Yol B display-only)

```
confidence         = max(0, min(1, revise(baseline, n, u, policy) × trust_score))   # Sprint 46, unchanged
agent_reputation   = last AGENT_REPUTATION_UPDATED reputation_score (last-wins)     # Sprint 48
```

**Yol B**: `agent_reputation` is display-only. It NEVER modifies the `confidence` field. The Sprint 46 contract (`revise() × trust_score`) is preserved exactly.

Verified by `test_reputation_does_not_change_confidence`:
- Add an `AGENT_REPUTATION_UPDATED` event to the log.
- `confidence` is byte-equal before and after.
- `agent_reputation` changes from `1.0` to the recorded score.

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `reputation/estimator.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `reputation/reducer.py` | same |
| `reputation/manager.py` | same |
| `reputation/events.py` | same |
| `reputation/model.py` | same |
| `revision/manager.py` | `ReputationManager(`, `ReputationReducer(` outside `_read_agent_reputation` |

Quality gate (`tests/test_reputation_quality_gate.py`) reads each determinism-critical file and asserts none of the forbidden tokens appear, and asserts the revision manager only reads reputation from the event log.

---

## Tests (36 new in 4 files)

### `tests/test_reputation.py` (23 tests)
- `reputation_score` composite formula and weighting (`success×0.5 + conf×0.3 + consistency×0.2`)
- `success_rate`, `mean_confidence`, `mean_duration`, `mean_retry` empty-list and populated cases
- `consistency` formula, `REPUTATION_MAX_RETRY` saturation, empty = 1.0
- `_stable_reputation_id` order-independence, agent distinction, `reputation-` prefix
- `make_payload` type coercion, range validation, rejection of malformed payloads
- `ReputationState` frozen/immutability, template version

### `tests/test_reputation_reducer.py` (9 tests)
- manager == reducer no events
- manager == reducer with samples
- manager == reducer other-agent ignored
- idempotent under repeated `apply` of the same event id
- last-wins aggregation across events
- invalid payload swallowed (no-op)
- `all_snapshots()` structure
- `known_agent_ids()` membership
- score composition matches estimator formula

### `tests/test_reputation_replay.py` (4 tests)
- `state["reputation"]` matches reducer projection
- replay round-trip exact dict equality
- byte-for-byte `reputation_score` match vs `ReputationReducer.snapshot()`
- multi-agent replay projection

### `tests/test_reputation_quality_gate.py` (3 tests)
- Forbidden tokens absent from 5 reputation module files
- `confidence` byte-equal before/after reputation event (Yol B display-only contract)
- Revision manager reads reputation from event log only (no `ReputationManager(`/`ReputationReducer(` instantiation)

### Existing tests — preserved
- All Sprint 47 tests pass unchanged
- `enable_reputation=False` preserves the Sprint 47 contract
- The new field has a backward-compatible default (`agent_reputation=1.0`)

**Test count: 1135 collected (full suite, no regressions). Sprint 48 adds 36 reputation-specific tests across 4 files.**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence | Medium | Both views consume the same event stream. Defaults (`agent_reputation=1.0`) preserve Sprint 47 behavior. Tests lock convergence for the full reputation log. |
| Recompute branch drift | Medium | Quality gate forbids `ReputationManager(`/`ReputationReducer(` in `revision/manager.py` outside `_read_agent_reputation`. |
| Determinism loss | Medium | Quality gate forbids `uuid7/datetime.now/random./time.time` in 5 reputation files. All formulas are pure math; `_stable_reputation_id` is sha256-based. |
| Stale reputation | Low | Last-wins means a single new `AGENT_REPUTATION_UPDATED` event supersedes all prior scores in the revision read-path. The reducer/manager still aggregate the full history. |
| Reputation explosion | Low | One event per pipeline run per agent. `enable_reputation=False` keeps it off by default. |

---

## Production impact

- `EventReplayEngine.replay()` now includes `state["reputation"]` in `final_state`. Replay-derived state and live-derived state share the same event-sourcing semantics.
- `RevisionManager.query()` and `RevisionReducer.snapshot()` now expose `agent_reputation`. The `confidence` field is unchanged.
- The system can finally say "I believe this (confidence X) but the executing agent's historical reliability is 0.78, so factor that into any downstream selection."

---

## Out-of-scope reminders (Sprint 49+)

- ❌ `ReputationManager(` / `ReputationReducer(` called inside `revision/manager.py` (Yol B: reputation comes from event log only)
- ❌ Reputation-weighted scheduling override (reputation is metadata; scheduler untouched)
- ❌ Multi-agent reputation fusion / cross-agent blend
- ❌ Bayesian posterior updates on reputation
- ❌ Per-task-type reputation (Sprint 52/53 with capabilities/learning)
- ❌ Real execution telemetry feeding `duration_ms` / `retry_count` (Sprint 50)
