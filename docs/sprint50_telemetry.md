# Sprint 50 — Runtime Telemetry Layer

## Goal

Sprint 50 makes agent execution performance a first-class measured signal. Where
Sprint 48 captured reputation from *task outcomes* and Sprint 49 captured
consensus from *votes*, Sprint 50 captures how the agent actually *ran*:
duration, retries, and success of each tool execution. After this sprint the
system can finally say:

- "Agent `codex` executed 50 tools: 48 succeeded, mean duration 1200 ms, mean
  retries 0.2. Its runtime score is 0.91."
- "I believe this (confidence X), the agent's reputation is 0.78 (Sprint 48),
  the consensus is 0.74 (Sprint 49), and its measured runtime quality is 0.91
  (Sprint 50)."

The revision chain is extended (read-only, no recompute) with a per-agent
runtime signal surfaced as `RevisionState.runtime_score`:

```
AGENT_RUNTIME_UPDATED → Revision (runtime_score, last-wins, default 1.0)
```

Runtime telemetry is **observation-only metadata**. In Sprint 50 the pipeline
stamps placeholder values (`duration_ms=0`, `retry_count=0`) because real
execution timing is wired in a later sprint; the *layer* and its convergence
guarantees are complete now. The Sprint 46 `confidence` contract is preserved.

## Architecture

```
Events
  ↓
TOOL_EXECUTION_STARTED            (tool call begins)
  ↓
TOOL_EXECUTION_COMPLETED          (sample: success, duration_ms, retry_count)
  ↓
AGENT_RUNTIME_UPDATED             (projection — computed by reducer)
  ↓
Revision (runtime_score)          (Sprint 50, last-wins, default 1.0)
  ↓
Snapshot (revision.runtime_score)
```

`AGENT_RUNTIME_UPDATED` is **not** emitted by the pipeline directly — it is a
*projection event* computed by the reducer/manager from the
`TOOL_EXECUTION_COMPLETED` stream. The pipeline emits only STARTED/COMPLETED.

## Scope

### In

1. New module `src/allbrain/telemetry/` (6 files: `__init__`, `model`, `metrics`, `events`, `reducer`, `manager`)
2. Three new event types: `TOOL_EXECUTION_STARTED`, `TOOL_EXECUTION_COMPLETED`, `AGENT_RUNTIME_UPDATED`
3. New pipeline step: `_telemetry_step` (off-by-default flag)
4. Revision integration (Yol B display-only): `RevisionState` gains the `runtime_score` field, `confidence` is **unchanged**
5. Replay binding (`TelemetryReducer` + `state["telemetry"]` projection in `EventReplayEngine`)
6. 33 tests across 4 files + quality gate

### Out of scope (Sprint 51+)

- Real execution timing (Sprint 50 stamps `duration_ms=0`, `retry_count=0` placeholders — actual instrumentation is future work)
- Per-tool telemetry aggregation (telemetry is per-agent, not per-tool)
- Telemetry-driven scheduling override (runtime is metadata; scheduler untouched)
- Percentile / tail-latency metrics (only mean is computed)
- Retry-attempt correlation (each COMPLETED carries its own aggregate `retry_count`)

---

## Resolved design decisions (Yol B display-only)

| Question | Decision |
|---|---|
| `revise()` signature | UNCHANGED — 4 args (Sprint 44 contract preserved) |
| `confidence` value | UNCHANGED — still `revise(...) × trust_score` (Sprint 46) |
| `runtime_score` formula | `success_rate×0.5 + duration_component×0.3 + retry_component×0.2`, clamped `[0, 1]` |
| `duration_component` | `1 − min(1, mean_duration / MAX_DURATION_MS)`; `MAX_DURATION_MS = 10000.0` |
| `retry_component` | `1 − min(1, mean_retry / MAX_RETRIES)`; `MAX_RETRIES = 5.0` |
| `runtime_score` default | `1.0` in revision when no `AGENT_RUNTIME_UPDATED` events (Yol B: no data = assume perfect execution) |
| `runtime_score` empty (reducer/manager) | `0.0` (zero samples = zero score) |
| Sample tuple | `(success: bool, duration_ms: float, retry_count: float)` |
| Sample source | `TOOL_EXECUTION_COMPLETED` payload |
| `AGENT_RUNTIME_UPDATED` role | Projection event — computed by reducer/manager, NOT emitted by the pipeline write-path |
| Telemetry scope | Per-agent (`agent_id`), not per-tool |
| Pipeline default flag | `enable_telemetry=False` |
| Pipeline stamp | `duration_ms=0.0`, `retry_count=0.0`, `success=True` (placeholder until instrumentation arrives) |
| Event source | Event log only (no recompute branch in revision layer) |

---

## Module changes

### `src/allbrain/telemetry/`

**`model.py`** — constants + frozen dataclass:
```python
TELEMETRY_TEMPLATE_VERSION = 1
MAX_DURATION_MS = 10000.0
MAX_RETRIES = 5.0
RUNTIME_SUCCESS_WEIGHT = 0.5
RUNTIME_DURATION_WEIGHT = 0.3
RUNTIME_RETRY_WEIGHT = 0.2

@dataclass(frozen=True)
class TelemetryState:
    agent_id: str
    execution_count: int
    success_rate: float
    mean_duration_ms: float
    mean_retry_count: float
    runtime_score: float
    analysis_id: str
    template_version: int = TELEMETRY_TEMPLATE_VERSION
```

**`metrics.py`** — Pure functions:
```python
def _stable_telemetry_id(agent_id, event_ids) -> str:
    """sha256(f"{agent_id}:{'|'.join(sorted(event_ids))}")[:12], prefix 'telemetry-'"""

def success_rate(samples) -> float:           # 0.0 for empty
def mean_duration(samples) -> float:          # 0.0 for empty
def mean_retry(samples) -> float:             # 0.0 for empty

def duration_component(mean_dur) -> float:
    """1 − min(1, mean_dur / MAX_DURATION_MS)."""

def retry_component(mean_ret) -> float:
    """1 − min(1, mean_ret / MAX_RETRIES)."""

def runtime_score(samples) -> float:
    """success_rate×0.5 + duration_component×0.3 + retry_component×0.2, clamped [0,1].
       0.0 for empty list."""
```

**`events.py`** — Three payload helpers:
```python
STARTED_REQUIRED_KEYS = frozenset({"agent_id", "task_id", "tool_name"})
COMPLETED_REQUIRED_KEYS = frozenset({"agent_id", "task_id", "tool_name",
                                     "duration_ms", "success", "retry_count"})
RUNTIME_REQUIRED_KEYS = frozenset({"agent_id", "mean_duration_ms",
                                   "success_rate", "mean_retry_count", "runtime_score"})

def validate_started_payload(payload) -> None: ...
def validate_completed_payload(payload) -> None: ...   # duration_ms/retry_count >= 0
def validate_runtime_payload(payload) -> None: ...     # score fields in [0,1]
def make_started_payload(*, agent_id, task_id, tool_name, ...) -> dict: ...
def make_completed_payload(*, agent_id, task_id, tool_name,
                           duration_ms, success, retry_count, ...) -> dict: ...
def make_runtime_updated_payload(*, agent_id, mean_duration_ms, success_rate,
                                 mean_retry_count, runtime_score_val, ...) -> dict: ...
```

**`reducer.py`** — `TelemetryReducer`:
- Idempotent via `_seen_ids`
- `TOOL_EXECUTION_COMPLETED`: append `(success, duration_ms, retry_count)` to per-agent sample list (validated)
- All other event types: no-op (`TOOL_EXECUTION_STARTED` and `AGENT_RUNTIME_UPDATED` are metadata — the reducer derives runtime from COMPLETED only)
- `snapshot(agent_id)`: same formula the manager uses
- `all_snapshots()`, `known_agent_ids()`

**`manager.py`** — `TelemetryManager.query`:
- `canonical_event_sort(events)`
- Collects samples from `TOOL_EXECUTION_COMPLETED` matching `agent_id`
- No recompute (Zorunlu): mirrors reducer exactly

### `src/allbrain/events/schemas.py`
Added: `TOOL_EXECUTION_STARTED = "tool_execution_started"`, `TOOL_EXECUTION_COMPLETED = "tool_execution_completed"`, `AGENT_RUNTIME_UPDATED = "agent_runtime_updated"` (EventType + SemanticEventType).

### `src/allbrain/revision/state.py`
Added `runtime_score: float = 1.0` field to `RevisionState` (backward-compatible default).

### `src/allbrain/revision/manager.py`
- New helper `_read_runtime_score(ordered) -> float`: scans for the last `AGENT_RUNTIME_UPDATED` `runtime_score`, defaults to `1.0` (last-wins)
- `confidence` is unchanged (Yol B display-only)
- Quality gate forbids `TelemetryManager(`/`TelemetryReducer(` outside `_read_runtime_score`

### `src/allbrain/replay/event_replay_engine.py`
- Import `TelemetryReducer`
- State dict: `"telemetry": {}`
- `_apply`: `telemetry_reducer.apply(event); state["telemetry"] = telemetry_reducer.all_snapshots()`
- `_copy_state`: includes `"telemetry"`

### `src/allbrain/runtime_core/pipeline.py`
- New flag: `enable_telemetry` (off-by-default)
- `_telemetry_step`: emits `TOOL_EXECUTION_STARTED` then `TOOL_EXECUTION_COMPLETED` with placeholder `duration_ms=0.0, success=True, retry_count=0.0` for the assigned agent/task
- `AGENT_RUNTIME_UPDATED` is NOT emitted here — it is a projection computed by the reducer
- `_result()` gains `telemetry` keyword arg
- Result dict gains `"telemetry"` key

---

## Convergence invariant

`TelemetryManager.query(events, agent_id=X) == TelemetryReducer.snapshot(agent_id=X)` for ALL event logs.

Locked by `test_telemetry_reducer.py`:
- manager == reducer no events
- manager == reducer with samples
- manager == reducer other-agent ignored
- runtime_score composition matches formula

---

## Replay determinism

`EventReplayEngine().replay(events)["final_state"]["telemetry"][X]["runtime_score"]` MUST equal `TelemetryReducer().snapshot(agent_id=X).runtime_score` byte-for-byte.

Locked by `test_telemetry_replay.py`.

---

## Revision integration (Yol B display-only)

```
confidence      = max(0, min(1, revise(baseline, n, u, policy) × trust_score))   # Sprint 46, unchanged
runtime_score   = last AGENT_RUNTIME_UPDATED runtime_score (last-wins)            # Sprint 50
```

**Yol B**: `runtime_score` is display-only. It NEVER modifies `confidence`. Verified by `test_does_not_change_confidence`: after an `AGENT_RUNTIME_UPDATED` event, `confidence` is byte-equal while `runtime_score` changes (e.g. to `0.5`).

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `telemetry/metrics.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `telemetry/reducer.py` | same |
| `telemetry/manager.py` | same |
| `telemetry/events.py` | same |
| `telemetry/model.py` | same |
| `revision/manager.py` | `TelemetryManager(`, `TelemetryReducer(` outside `_read_runtime_score` |

Quality gate (`tests/test_telemetry_quality_gate.py`):
- `test_no_nondeterminism` — forbidden tokens absent from 5 telemetry files
- `test_does_not_change_confidence` — Yol B display-only contract
- `test_no_recompute` — revision reads runtime from event log only

---

## Tests (33 new in 4 files)

### `tests/test_telemetry.py` (20 tests)
- `runtime_score` weighting (`success×0.5 + duration_comp×0.3 + retry_comp×0.2`), clamping
- `duration_component` / `retry_component` saturation at `MAX_DURATION_MS` / `MAX_RETRIES`
- `success_rate` / `mean_duration` / `mean_retry` empty and populated cases
- `_stable_telemetry_id` order-independence, agent distinction, `telemetry-` prefix
- `make_started_payload` / `make_completed_payload` / `make_runtime_updated_payload` type coercion, validation, rejection
- `TelemetryState` frozen/immutability, template version

### `tests/test_telemetry_reducer.py` (7 tests)
- manager == reducer no events
- manager == reducer with samples
- manager == reducer other-agent ignored
- idempotent under repeated apply
- invalid completed payload swallowed
- `all_snapshots()` structure
- `known_agent_ids()` membership

### `tests/test_telemetry_replay.py` (3 tests)
- `state["telemetry"]` matches reducer projection
- replay round-trip exact dict equality
- byte-for-byte `runtime_score` match

### `tests/test_telemetry_quality_gate.py` (3 tests)
- No nondeterminism tokens in 5 telemetry files
- `confidence` byte-equal before/after runtime event
- Revision manager reads runtime from event log only

### Existing tests — preserved
- All Sprint 49 tests pass unchanged
- `enable_telemetry=False` preserves the Sprint 49 contract
- The new field has a backward-compatible default (`runtime_score=1.0`)

**Test count: 1135 collected (full suite, no regressions). Sprint 50 adds 33 telemetry-specific tests across 4 files.**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence | Medium | Both views consume the same COMPLETED stream. Default (`runtime_score=1.0`) preserves Sprint 49 behavior. |
| Recompute branch drift | Medium | Quality gate forbids `TelemetryManager(`/`TelemetryReducer(` in `revision/manager.py` outside `_read_runtime_score`. |
| Determinism loss | Medium | Quality gate forbids nondeterminism tokens in 5 telemetry files. `_stable_telemetry_id` is sha256-based. |
| Placeholder values | Low | `duration_ms=0` / `retry_count=0` placeholders produce `duration_component=1.0` / `retry_component=1.0` (perfect), so Sprint 50 telemetry looks optimistic until real instrumentation arrives. Documented; no correctness risk to replay. |
| STARTED event underuse | Low | `TOOL_EXECUTION_STARTED` is recorded but not consumed by the reducer. It is a lifecycle marker for future span-correlation work. |

---

## Production impact

- `EventReplayEngine.replay()` now includes `state["telemetry"]` in `final_state`.
- `RevisionManager.query()` and `RevisionReducer.snapshot()` now expose `runtime_score`. The `confidence` field is unchanged.
- The system can finally say "the agent's measured runtime quality is 0.91" — the first time *execution* performance (not task outcome, not vote) is a recorded signal.

---

## Out-of-scope reminders (Sprint 51+)

- ❌ `TelemetryManager(` / `TelemetryReducer(` called inside `revision/manager.py` (Yol B: runtime comes from event log only)
- ❌ Real execution timing (`duration_ms=0` placeholder until instrumentation)
- ❌ Per-tool telemetry aggregation
- ❌ Telemetry-driven scheduling override
- ❌ Percentile / tail-latency metrics (mean only)
- ❌ Retry-attempt correlation
