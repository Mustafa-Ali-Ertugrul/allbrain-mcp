# Sprint 52 — Capability Matching Layer

## Goal

Sprint 52 shifts Batch 2 from *agent-level* signals (reputation, runtime,
consensus — Batch 1) to *capability-level* signals: does an agent's *declared
capability* match the *task type*? After this sprint the system can finally say:

- "Task `t_42` is an `implementation` task. Agent `codex` has declared the
  `implementation` capability (weight 1.0) — exact match, score 1.0. Agent
  `qwen` has `code_review` (weight 0.8) — partial match (`code` ⊂
  `implementation` normalized), score 0.4."
- "I recommend `codex` because its declared capability is an exact match."

The revision chain is extended (read-only, no recompute) with a per-agent
capability-match signal surfaced as `RevisionState.capability_score`:

```
CAPABILITY_MATCHED → Revision (capability_score, last-wins, default 1.0)
```

Capability matching is **declarative**: agents register capabilities
(`AGENT_CAPABILITY_REGISTERED`), the pipeline classifies a task
(`TASK_CLASSIFIED`), then emits match events. No learning yet — that is Sprint
53. The Sprint 46 `confidence` contract is preserved.

## Architecture

```
AGENT_CAPABILITY_REGISTERED   (agent declares capability + weight)
  ↓
TASK_CLASSIFIED               (task → task_type)
  ↓
CAPABILITY_MATCHED            (per agent: match_score, match_kind)
  ↓
Revision (capability_score)   (Sprint 52, last-wins, default 1.0)
  ↓
Snapshot (revision.capability_score)
```

## Scope

### In

1. New module `src/allbrain/capabilities/` (6 files: `__init__`, `model`, `scorer`, `events`, `reducer`, `manager`)
2. Three new event types: `AGENT_CAPABILITY_REGISTERED`, `TASK_CLASSIFIED`, `CAPABILITY_MATCHED`
3. New pipeline step: `_capability_step` (off-by-default flag)
4. Revision integration (Yol B display-only): `RevisionState` gains the `capability_score` field, `confidence` is **unchanged**
5. Replay binding (`CapabilityReducer` + `state["capability"]` projection in `EventReplayEngine`)
6. 12 tests in `test_capabilities.py`

### Out of scope (Sprint 53+)

- Learned capability (`match_score` is purely declarative in Sprint 52; learning is Sprint 53)
- Per-`(agent, task_type)` capability records (Sprint 52 is per-agent match against a single task type per run)
- Capability drift / decay (Sprint 54)
- Capability registration via MCP tool (registration events exist; no dedicated tool yet)

---

## Resolved design decisions (Yol B display-only)

| Question | Decision |
|---|---|
| `revise()` signature | UNCHANGED — 4 args (Sprint 44 contract preserved) |
| `confidence` value | UNCHANGED — still `revise(...) × trust_score` (Sprint 46) |
| `match_score` formula | mean over declared capabilities of `kind_weight × capability_weight`; best `match_kind` returned |
| Kind weights | `EXACT_MATCH = 1.0`, `PARTIAL_MATCH = 0.5`, `NO_MATCH = 0.0` |
| `match_kind` rule | exact: normalized equal; partial: one contains the other; none: otherwise |
| `normalize_task_type` | `re.sub(r"[^a-z0-9]", "", task_type.lower())` — strip non-alphanumeric, lowercase |
| `match_kind` precedence | `exact` > `partial` > `none` (the *kind* reported is the best kind seen, even if avg is lowered by non-matches) |
| `capability_score` default | `1.0` in revision when no `CAPABILITY_MATCHED` events |
| Match scope | Per-agent against a single task type |
| Pipeline default flag | `enable_capabilities=False` |
| Event source | Event log only (no recompute branch in revision layer) |

---

## Module changes

### `src/allbrain/capabilities/`

**`model.py`** — constants + frozen dataclass:
```python
CAPABILITY_TEMPLATE_VERSION = 1
EXACT_MATCH = 1.0
PARTIAL_MATCH = 0.5
NO_MATCH = 0.0
MATCH_EPSILON = 1e-9

@dataclass(frozen=True)
class CapabilityState:
    agent_id: str
    capability_count: int
    task_type: str
    match_score: float
    match_kind: str
    analysis_id: str
    template_version: int = CAPABILITY_TEMPLATE_VERSION
```

**`scorer.py`** — Pure functions:
```python
def _stable_capability_id(agent_id, event_ids) -> str:
    """sha256(f"{agent_id}:{'|'.join(sorted(event_ids))}")[:12], prefix 'capability-'"""

def normalize_task_type(task_type) -> str:
    """re.sub(r'[^a-z0-9]', '', task_type.lower())."""

def match_kind(agent_capability, task_type) -> str:
    """'exact' | 'partial' | 'none' based on normalized containment."""

def match_score(*, agent_capabilities, task_type) -> tuple[float, str]:
    """For each (cap_name, weight): score += kind_weight × weight.
       Returns (mean_score clamped [0,1], best_kind).
       Empty capability list → (0.0, 'none')."""
```

**`events.py`** — Three payload helpers:
```python
REG_KEYS = frozenset({"agent_id", "capability", "weight"})
CLASSIFIED_KEYS = frozenset({"task_id", "task_type"})
MATCHED_KEYS = frozenset({"agent_id", "task_type", "match_score", "match_kind"})

def validate_registered(payload) -> None: ...    # weight in [0,1]
def validate_classified(payload) -> None: ...
def validate_matched(payload) -> None: ...       # match_score in [0,1]
def make_registered_payload(*, agent_id, capability, weight, ...) -> dict: ...
def make_classified_payload(*, task_id, task_type, ...) -> dict: ...
def make_matched_payload(*, agent_id, task_type, match_score, match_kind, ...) -> dict: ...
```

**`reducer.py`** — `CapabilityReducer`:
- Idempotent via `_seen_ids`
- `CAPABILITY_MATCHED`: append `(match_score, match_kind)` to per-agent list, record task_type
- All other event types: no-op (`REGISTERED` and `CLASSIFIED` are inputs consumed at write-time by the pipeline, not by the reducer)
- `snapshot(agent_id)`: best `(score, kind)` over recorded matches; empty → `(0.0, "none")`
- `all_snapshots()`, `known_agent_ids()`

**`manager.py`** — `CapabilityManager.query`:
- `canonical_event_sort(events)`
- Collects `CAPABILITY_MATCHED` events for `agent_id`; returns best `(match_score, match_kind)`
- No recompute (Zorunlu): mirrors reducer exactly
- `known_agent_ids(events)` / `known_keys(events)` (the latter returns `(agent_id, task_type)` pairs, consumed by Sprints 53–56)

### `src/allbrain/events/schemas.py`
Added: `AGENT_CAPABILITY_REGISTERED = "agent_capability_registered"`, `TASK_CLASSIFIED = "task_classified"`, `CAPABILITY_MATCHED = "capability_matched"` (EventType + SemanticEventType).

### `src/allbrain/revision/state.py`
Added `capability_score: float = 1.0` field to `RevisionState` (backward-compatible default).

### `src/allbrain/revision/manager.py`
- New helper `_read_capability_score(ordered) -> float`: scans for the last `CAPABILITY_MATCHED` `match_score`, defaults to `1.0` (last-wins)
- `confidence` is unchanged (Yol B display-only)

### `src/allbrain/replay/event_replay_engine.py`
- Import `CapabilityReducer`
- State dict: `"capability": {}`
- `_apply`: `capability_reducer.apply(event); state["capability"] = capability_reducer.all_snapshots()`
- `_copy_state`: includes `"capability"`

### `src/allbrain/runtime_core/pipeline.py`
- New flag: `enable_capabilities` (off-by-default)
- `_capability_step`:
  1. Reads registered agent capabilities from the log
  2. Emits `TASK_CLASSIFIED` for the scheduler's task
  3. For each known agent: `match_score(agent_capabilities, task_type)` → emits `CAPABILITY_MATCHED` (only if `match_score > 0.0`)
- `_result()` gains `capability` keyword arg; result dict gains `"capability"` key

---

## Convergence invariant

`CapabilityManager.query(events, agent_id=X) == CapabilityReducer.snapshot(agent_id=X)` for ALL event logs.

Verified in `test_capabilities.py` (manager/reducer agreement cases).

---

## Replay determinism

`EventReplayEngine().replay(events)["final_state"]["capability"][X]["match_score"]` MUST equal `CapabilityReducer().snapshot(agent_id=X).match_score` byte-for-byte.

---

## Revision integration (Yol B display-only)

```
confidence         = max(0, min(1, revise(baseline, n, u, policy) × trust_score))   # Sprint 46, unchanged
capability_score   = last CAPABILITY_MATCHED match_score (last-wins)                # Sprint 52
```

**Yol B**: `capability_score` is display-only. It NEVER modifies `confidence`.

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `capabilities/scorer.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `capabilities/reducer.py` | same |
| `capabilities/manager.py` | same |
| `capabilities/events.py` | same |
| `capabilities/model.py` | same |

(The capabilities module has no dedicated quality-gate test file in Sprint 52; determinism is enforced by the shared `test_foundations.py` ordering invariants and the manager/reducer convergence cases. Sprint 53 adds the learning quality gate.)

---

## Tests (12 new in 1 file)

### `tests/test_capabilities.py` (12 tests)
- `match_kind` exact/partial/none classification
- `normalize_task_type` punctuation stripping, case folding
- `match_score` weighting (`kind × weight`), averaging, clamping
- empty capability list → `(0.0, "none")`
- kind precedence (exact reported even if partial/none also present)
- `make_*_payload` validation, type coercion, rejection
- `CapabilityState` frozen/immutability, template version
- manager == reducer agreement (no events, with matches, other-agent ignored)

### Existing tests — preserved
- All Sprint 51 tests pass unchanged
- `enable_capabilities=False` preserves the Sprint 51 contract
- The new field has a backward-compatible default (`capability_score=1.0`)

**Test count: 1135 collected (full suite, no regressions). Sprint 52 adds 12 capability-specific tests in 1 file.**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence | Medium | Both views consume the same MATCHED stream. Default (`capability_score=1.0`) preserves Sprint 51 behavior. |
| Determinism loss | Low | Quality gate is implicit in Sprint 52; `_stable_capability_id` is sha256-based; `normalize_task_type` is pure regex. |
| Substring false positives | Low | `match_kind` partial = normalized containment. `code` ⊂ `implementation` (normalized `code` ⊂ `implementation`) is a known loose match; documented. |
| Declarative staleness | Medium | Capabilities are declared, not learned. A misdeclared capability produces a wrong match until Sprint 53 learning corrects it. |
| Missing quality gate | Low | No dedicated `test_capability_quality_gate.py` in Sprint 52. Sprint 53's learning quality gate covers the broader module. |

---

## Production impact

- `EventReplayEngine.replay()` now includes `state["capability"]` in `final_state`.
- `RevisionManager.query()` and `RevisionReducer.snapshot()` now expose `capability_score`. The `confidence` field is unchanged.
- The system can finally say "agent `codex` is an exact capability match for this `implementation` task" — the first time *task-fit* (not past performance) is a recorded signal.

---

## Out-of-scope reminders (Sprint 53+)

- ❌ Learned capability (declarative only in Sprint 52; EMA learning is Sprint 53)
- ❌ Capability drift / decay (Sprint 54 dynamics)
- ❌ Per-`(agent, task_type)` capability tables (Sprint 52 is per-agent vs single task type)
- ❌ Capability registration MCP tool
- ❌ Capability-weighted scheduling override (still recommendation-only)
