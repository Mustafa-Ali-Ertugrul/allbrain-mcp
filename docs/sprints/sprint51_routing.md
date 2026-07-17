# Sprint 51 — Signal Selection & Routing Layer

## Goal

Sprint 51 is the **synthesis layer** of Batch 1: it fuses the four agent-level
signals from Sprints 48–50 plus Sprint 46's trust into a single per-agent
selection score, and records *which* agent the system would recommend for a task
type. After this sprint the system can finally say:

- "For `implementation` tasks I scored three agents: `codex` 0.82, `claude`
  0.71, `qwen` 0.55. I recommend `codex`."
- "The recommendation is `advisory-only` — it uses event-sourced reputation,
  runtime, calibrated trust, and consensus, but it does NOT change the actual
  scheduler assignment."

The revision chain is extended (read-only, no recompute) with a per-task-type
selection signal surfaced as `RevisionState.selection_score`:

```
AGENT_SELECTED → Revision (selection_score, last-wins, default 1.0)
```

Routing is **recommendation-only** in Sprint 51. The actual assignment is still
made by `DeterministicScheduler`; routing records *what the system would have
chosen* given the accumulated signals, for observability and future closed-loop
learning.

## Architecture

```
Reputation (Sprint 48)  ─┐
Runtime (Sprint 50)      ─┼─→ selection_score (per agent)
Trust (Sprint 46)        ─┤
Consensus (Sprint 49)    ─┘
                                   ↓
AGENT_SELECTION_REQUESTED           (task classification)
  ↓
AGENT_SELECTION_SCORED   (one per candidate agent)
  ↓
AGENT_SELECTED           (best agent + score)
  ↓
Revision (selection_score)  (Sprint 51, last-wins, default 1.0)
  ↓
Snapshot (revision.selection_score)
```

## Scope

### In

1. New module `src/allbrain/routing/` (6 files: `__init__`, `model`, `scorer`, `events`, `reducer`, `manager`)
2. Three new event types: `AGENT_SELECTION_REQUESTED`, `AGENT_SELECTION_SCORED`, `AGENT_SELECTED`
3. New pipeline step: `_routing_step` (off-by-default flag)
4. Revision integration (Yol B display-only): `RevisionState` gains the `selection_score` field, `confidence` is **unchanged**
5. Replay binding (`RoutingReducer` + `state["routing"]` projection in `EventReplayEngine`)
6. 26 tests across 4 files + quality gate

### Out of scope (Sprint 52+)

- Capability-aware scoring (`extended_selection_score`, `adaptive_selection_score` — added to `scorer.py` but gated behind `enable_capabilities`/`enable_learning`, documented in Sprint 52/53)
- Dynamics/causal/fusion scoring variants (`dynamics_selection_score`, `causal_selection_score`, `unified_decision_score` — Sprint 54/55/56)
- Routing *overriding* the scheduler (recommendation-only in Sprint 51)
- Multi-task-type routing tables (one recommendation per pipeline run)

---

## Resolved design decisions (Yol B display-only)

| Question | Decision |
|---|---|
| `revise()` signature | UNCHANGED — 4 args (Sprint 44 contract preserved) |
| `confidence` value | UNCHANGED — still `revise(...) × trust_score` (Sprint 46) |
| `selection_score` formula (Sprint 51) | `reputation×0.35 + runtime×0.35 + calibrated_trust×0.20 + consensus×0.10`, clamped `[0, 1]` |
| `selection_score` default | `1.0` in revision when no `AGENT_SELECTED` events |
| Score scope | Per `(agent, task_type)` — every SCORED event carries both |
| `best_agent` tie-break | `sorted(items, key=(-score, agent_id))` — highest score, then lexicographic agent id |
| Known agents | Union of reputation + telemetry participants (`rep_mgr.known_agent_ids ∪ tel_mgr.known_agent_ids`) |
| Recommendation vs assignment | **Advisory only** — `AGENT_SELECTED` does NOT mutate the scheduler's assignment |
| Pipeline default flag | `enable_routing=False` |
| Forward-ref scorers | `scorer.py` contains `extended/adaptive/dynamics/causal/unified` functions for later sprints; Sprint 51 only uses base `selection_score` |
| Event source | Event log only (no recompute branch in revision layer) |

---

## Module changes

### `src/allbrain/routing/`

**`model.py`** — constants + frozen dataclass:
```python
ROUTING_TEMPLATE_VERSION = 1
ROUTING_REPUTATION_WEIGHT = 0.35
ROUTING_RUNTIME_WEIGHT = 0.35
ROUTING_TRUST_WEIGHT = 0.20
ROUTING_CONSENSUS_WEIGHT = 0.10
ROUTING_TIE_EPSILON = 1e-9

@dataclass(frozen=True)
class RoutingState:
    task_type: str
    selected_agent: str | None
    selection_score: float
    candidate_count: int
    analysis_id: str
    template_version: int = ROUTING_TEMPLATE_VERSION
```

**`scorer.py`** — Pure functions (Sprint 51 surface):
```python
def _stable_routing_id(task_type, event_ids) -> str:
    """sha256(f"{task_type}:{'|'.join(sorted(event_ids))}")[:12], prefix 'routing-'"""

def selection_score(*, reputation, runtime_score, calibrated_trust,
                    consensus_score) -> float:
    """rep×0.35 + runtime×0.35 + trust×0.20 + consensus×0.10, clamped [0,1].
       This is the ONLY scorer used by the Sprint 51 routing step."""

def best_agent(scored: dict[str, float]) -> str | None:
    """max by score; ties broken by lexicographic agent_id; None for empty."""

def rank_agents(scored) -> list[tuple[str, float]]: ...   # full ranked list
def score_bounds(v) -> float: ...                          # clamp [0,1]
```

> **Forward references (NOT used in Sprint 51):** `scorer.py` also defines
> `extended_selection_score` (Sprint 52), `adaptive_selection_score` (Sprint 53),
> `dynamics_selection_score` (Sprint 54), `causal_selection_score` (Sprint 55),
> `unified_decision_score` (Sprint 56). These are pre-staged for later sprints;
> the Sprint 51 pipeline step calls only `selection_score`.

**`events.py`** — Three payload helpers:
```python
REQ_KEYS = frozenset({"task_id", "task_type", "context_key"})
SCORED_KEYS = frozenset({"agent_id", "task_type", "selection_score",
                         "reputation", "runtime_score", "calibrated_trust"})
SELECTED_KEYS = frozenset({"task_id", "task_type", "agent_id", "selection_score"})

def validate_req(payload) -> None: ...
def validate_scored(payload) -> None: ...     # score fields in [0,1]
def validate_selected(payload) -> None: ...   # selection_score in [0,1]
def make_req_payload(*, task_id, task_type, context_key, ...) -> dict: ...
def make_scored_payload(*, agent_id, task_type, selection_score,
                        reputation, runtime_score, calibrated_trust, rank=0, ...) -> dict: ...
def make_selected_payload(*, task_id, task_type, agent_id, selection_score, ...) -> dict: ...
```

**`reducer.py`** — `RoutingReducer`:
- Idempotent via `_seen_ids`
- `AGENT_SELECTION_SCORED`: record per-agent `selection_score` for `task_type`
- `AGENT_SELECTED`: record the selected agent + score for `task_type` (last-wins)
- All other event types: no-op
- `snapshot(task_type)`: returns the selected agent + score; `selected_agent=None` if none recorded
- `all_snapshots()`, `known_task_types()`

**`manager.py`** — `RoutingManager.query`:
- `canonical_event_sort(events)`
- Collects SCORED + SELECTED events for `task_type`
- No recompute (Zorunlu): mirrors reducer exactly

### `src/allbrain/events/schemas.py`
Added: `AGENT_SELECTION_REQUESTED = "agent_selection_requested"`, `AGENT_SELECTION_SCORED = "agent_selection_scored"`, `AGENT_SELECTED = "agent_selected"` (EventType + SemanticEventType).

### `src/allbrain/revision/state.py`
Added `selection_score: float = 1.0` field to `RevisionState` (backward-compatible default).

### `src/allbrain/revision/manager.py`
- New helper `_read_selected_agent_score(ordered) -> float`: scans for the last `AGENT_SELECTED` `selection_score`, defaults to `1.0` (last-wins)
- `confidence` is unchanged (Yol B display-only)

### `src/allbrain/replay/event_replay_engine.py`
- Import `RoutingReducer`
- State dict: `"routing": {}`
- `_apply`: `routing_reducer.apply(event); state["routing"] = routing_reducer.all_snapshots()`
- `_copy_state`: includes `"routing"`

### `src/allbrain/runtime_core/pipeline.py`
- New flag: `enable_routing` (off-by-default)
- `_routing_step`:
  1. Emits `AGENT_SELECTION_REQUESTED` for the task
  2. For each known agent: queries `ReputationManager`, `TelemetryManager`, `RevisionManager` (calibrated_trust + consensus_score), computes `selection_score(...)`, emits `AGENT_SELECTION_SCORED`
  3. `best_agent(scored)` → emits `AGENT_SELECTED` with `impact_score=score`
- The pipeline step accepts forward-looking flags (`enable_capabilities`, `enable_learning`, `enable_causal`, `enable_dynamics`, `enable_fusion`, `enable_decision_engine`, etc.) and will route to the later-sprint scorers when they are enabled; in Sprint 51 only the base path is active
- `_result()` gains `routing` keyword arg; result dict gains `"routing"` key

---

## Convergence invariant

`RoutingManager.query(events, task_type=X) == RoutingReducer.snapshot(task_type=X)` for ALL event logs.

Locked by `test_routing_reducer.py`:
- manager == reducer no events
- manager == reducer with scored agents
- manager == reducer selected preferred
- manager == reducer other-task-type ignored

---

## Replay determinism

`EventReplayEngine().replay(events)["final_state"]["routing"][X]["selection_score"]` MUST equal `RoutingReducer().snapshot(task_type=X).selection_score` byte-for-byte.

Locked by `test_routing_replay.py`.

---

## Revision integration (Yol B display-only)

```
confidence        = max(0, min(1, revise(baseline, n, u, policy) × trust_score))   # Sprint 46, unchanged
selection_score   = last AGENT_SELECTED selection_score (last-wins)                # Sprint 51
```

**Yol B**: `selection_score` is display-only. It NEVER modifies `confidence`. Verified by `test_does_not_change_confidence`: after an `AGENT_SELECTED` event, `confidence` is byte-equal while `selection_score` changes (e.g. to `0.7`).

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `routing/scorer.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `routing/reducer.py` | same |
| `routing/manager.py` | same |
| `routing/events.py` | same |
| `routing/model.py` | same |
| `revision/manager.py` | `RoutingManager(`, `RoutingReducer(` outside `_read_selected_agent_score` |

Quality gate (`tests/test_routing_quality_gate.py`):
- `test_no_nondeterminism` — forbidden tokens absent from 5 routing files
- `test_does_not_change_confidence` — Yol B display-only contract
- `test_no_recompute` — revision reads selection from event log only

---

## Tests (26 new in 4 files)

### `tests/test_routing.py` (14 tests)
- `selection_score` weighting (`rep×0.35 + runtime×0.35 + trust×0.20 + consensus×0.10`), clamping
- `best_agent` selection, empty → None, tie-break by agent_id
- `rank_agents` ordering
- `score_bounds` clamping
- `make_*_payload` validation, type coercion, rejection of malformed payloads
- `RoutingState` frozen/immutability, template version

### `tests/test_routing_reducer.py` (6 tests)
- manager == reducer no events
- manager == reducer with scored agents
- manager == reducer selected preferred
- manager == reducer other-task-type ignored
- idempotent under repeated apply
- `all_snapshots()` / `known_task_types()`

### `tests/test_routing_replay.py` (3 tests)
- `state["routing"]` matches reducer projection
- replay round-trip exact dict equality
- byte-for-byte `selection_score` match

### `tests/test_routing_quality_gate.py` (3 tests)
- No nondeterminism tokens in 5 routing files
- `confidence` byte-equal before/after selection event
- Revision manager reads selection from event log only

### Existing tests — preserved
- All Sprint 50 tests pass unchanged
- `enable_routing=False` preserves the Sprint 50 contract
- The new field has a backward-compatible default (`selection_score=1.0`)

**Test count: 1135 collected (full suite, no regressions). Sprint 51 adds 26 routing-specific tests across 4 files.**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence | Medium | Both views consume the same SCORED+SELECTED stream. Default (`selection_score=1.0`) preserves Sprint 50 behavior. |
| Recompute branch drift | Medium | Quality gate forbids `RoutingManager(`/`RoutingReducer(` in `revision/manager.py` outside `_read_selected_agent_score`. |
| Determinism loss | Medium | Quality gate forbids nondeterminism tokens. `_stable_routing_id` is sha256-based; `best_agent` tie-break is deterministic. |
| Advisory/assignment confusion | Medium | Documented as recommendation-only. The scheduler (`_schedule`) is untouched by `_routing_step`. A future sprint may close the loop. |
| Forward-ref scorer misuse | Low | `scorer.py` pre-stages later-sprint functions, but `_routing_step` calls only `selection_score` unless the corresponding `enable_*` flag is on. |

---

## Production impact

- `EventReplayEngine.replay()` now includes `state["routing"]` in `final_state`.
- `RevisionManager.query()` and `RevisionReducer.snapshot()` now expose `selection_score`. The `confidence` field is unchanged.
- The system can finally say "given reputation + runtime + trust + consensus, I recommend agent `codex` for this task" — the first time the four Batch-1 signals are fused into a single selection recommendation.

---

## Out-of-scope reminders (Sprint 52+)

- ❌ `RoutingManager(` / `RoutingReducer(` called inside `revision/manager.py` (Yol B: selection comes from event log only)
- ❌ Routing overriding the scheduler (recommendation-only)
- ❌ Capability/learning/dynamics/causal/fusion scoring (those are Sprint 52–56, gated by `enable_*` flags)
- ❌ Multi-task-type routing tables
- ❌ Closed-loop learning from routing recommendations vs actual outcomes (future)
