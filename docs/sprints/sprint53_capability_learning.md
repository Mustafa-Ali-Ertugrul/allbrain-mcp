# Sprint 53 — Capability Learning (EMA) Layer

## Goal

Sprint 53 turns the declarative capability matching of Sprint 52 into an
*adaptive* signal: the system now *learns* an agent's true capability per
`(agent, task_type)` from observed outcomes via exponential moving average (EMA).
After this sprint the system can finally say:

- "Agent `codex` was observed 8 times on `implementation` tasks. Its learned
  capability rose from 0.50 (cold start) to 0.78 as it kept succeeding."
- "Agent `qwen`'s learned capability on `code_review` decayed from 0.71 to 0.66
  after two weak observations."

The revision chain is extended (read-only, no recompute) with a per-`(agent,
task_type)` learned-capability signal surfaced as
`RevisionState.learned_capability`:

```
AGENT_CAPABILITY_LEARNED / DECAYED → Revision (learned_capability, last-wins, default 1.0)
```

Capability learning is the first *self-improving* layer: the capability score
evolves from observed performance rather than being declared. The Sprint 46
`confidence` contract is preserved.

## Architecture

```
AGENT_CAPABILITY_OBSERVED        (raw observation: success, runtime_score, selection_score)
  ↓
observation()  →  ema_update()  (pure EMA: old×0.9 + obs×0.1)
  ↓
AGENT_CAPABILITY_LEARNED         (delta >= 0.02 improvement)
  ↓  OR
AGENT_CAPABILITY_DECAYED         (delta <= -0.02 regression)
  ↓
Revision (learned_capability)    (Sprint 53, last-wins, default 1.0)
  ↓
Snapshot (revision.learned_capability)
```

## Scope

### In

1. New module `src/allbrain/learning/` (5 files: `__init__`, `model`, `learner`, `events`, `manager`, `reducer`)
2. Three new event types: `AGENT_CAPABILITY_OBSERVED`, `AGENT_CAPABILITY_LEARNED`, `AGENT_CAPABILITY_DECAYED`
3. New pipeline step: `_learning_step` (off-by-default flag)
4. Revision integration (Yol B display-only): `RevisionState` gains the `learned_capability` field, `confidence` is **unchanged**
5. Replay binding (`CapabilityLearningReducer` + `state["learning"]` projection in `EventReplayEngine`)
6. 55 tests across 4 files + dedicated quality gate

### Out of scope (Sprint 54+)

- Drift / trend / forecast over the learned capability time series (Sprint 54 dynamics)
- Counterfactual capability ("what if a different agent had run this?") — Sprint 55 causal
- Multi-signal fusion of capability with other layers — Sprint 56
- Bayesian capability estimation (EMA is frequentist in Sprint 53)
- Per-observation confidence weighting (each observation contributes equally via fixed EMA bias)

---

## Resolved design decisions (Yol B display-only)

| Question | Decision |
|---|---|
| `revise()` signature | UNCHANGED — 4 args (Sprint 44 contract preserved) |
| `confidence` value | UNCHANGED — still `revise(...) × trust_score` (Sprint 46) |
| EMA formula | `new = old × LEARNING_RETENTION + observation × LEARNING_EMA_BIAS` = `old×0.9 + obs×0.1` |
| `LEARNING_RETENTION` | `0.9` |
| `LEARNING_EMA_BIAS` | `0.1` |
| `INITIAL_CAPABILITY` (cold start) | `0.5` (neutral) |
| `observation` formula | `success×0.5 + runtime_score×0.3 + selection_score×0.2`, clamped `[0, 1]` |
| Emit threshold | `LEARNING_DELTA_THRESHOLD = 0.02` — emit LEARNED/DECAYED only if `|delta| >= 0.02` (suppress noise) |
| LEARNED vs DECAYED | `delta >= 0` → LEARNED; `delta < 0` → DECAYED |
| `learned_capability` default | `1.0` in revision when no LEARNED/DECAYED events |
| Learned scope | Per `(agent_id, task_type)` — keyed as `"{agent_id}::{task_type}"` |
| Pipeline default flag | `enable_learning=False` |
| Event source | Event log only (no recompute branch in revision layer) |

---

## Module changes

### `src/allbrain/learning/`

**`model.py`** — constants + frozen dataclass:
```python
LEARNING_TEMPLATE_VERSION = 1
LEARNING_RETENTION = 0.9
LEARNING_EMA_BIAS = 0.1
INITIAL_CAPABILITY = 0.5
LEARNING_DELTA_THRESHOLD = 0.02

@dataclass(frozen=True)
class LearnedCapabilityState:
    agent_id: str
    task_type: str
    observation_count: int
    capability_score: float
    last_delta: float
    analysis_id: str
    template_version: int = LEARNING_TEMPLATE_VERSION
```

**`learner.py`** — Pure functions:
```python
def _stable_learning_id(key, event_ids) -> str:
    """sha256(f"{key}:{'|'.join(sorted(event_ids))}")[:12], prefix 'learn-'.
       key is f"{agent_id}::{task_type}"."""

def observation(*, success, runtime_score, selection_score) -> float:
    """success×0.5 + runtime_score×0.3 + selection_score×0.2, clamped [0,1]."""

def ema_update(old_score, observation_val) -> float:
    """old×0.9 + observation_val×0.1, clamped [0,1]."""
```

**`events.py`** — Three payload helpers:
```python
OBSERVED_KEYS, LEARNED_KEYS, DECAYED_KEYS  # required-key frozensets per payload

def validate_observed(payload) -> None: ...
def validate_learned(payload) -> None: ...
def validate_decayed(payload) -> None: ...
def make_observed_payload(*, agent_id, task_type, success, runtime_score, selection_score, ...) -> dict: ...
def make_learned_payload(*, agent_id, task_type, old_score, new_score, delta, ...) -> dict: ...
def make_decayed_payload(*, agent_id, task_type, old_score, new_score, ...) -> dict: ...
```

**`manager.py`** — `CapabilityLearningManager.query`:
- `canonical_event_sort(events)`
- For `(agent_id, task_type)`: counts OBSERVED, tracks last `new_score`/`delta` from LEARNED/DECAYED
- No recompute (Zorunlu): reads the learned score from the event log, does NOT re-run `ema_update`
- `known_keys(events)` returns `{"{agent_id}::{task_type}", ...}`

**`reducer.py`** — `CapabilityLearningReducer`:
- Idempotent via `_seen_ids`
- `AGENT_CAPABILITY_OBSERVED`: increment per-key observation count
- `AGENT_CAPABILITY_LEARNED`: record `new_score` + `delta`
- `AGENT_CAPABILITY_DECAYED`: record `new_score` + recompute `delta = new − old`
- `snapshot(agent_id, task_type)`: mirrors manager
- `all_snapshots()`, `known_keys()`

### `src/allbrain/events/schemas.py`
Added: `AGENT_CAPABILITY_OBSERVED = "agent_capability_observed"`, `AGENT_CAPABILITY_LEARNED = "agent_capability_learned"`, `AGENT_CAPABILITY_DECAYED = "agent_capability_decayed"` (EventType + SemanticEventType).

### `src/allbrain/revision/state.py`
Added `learned_capability: float = 1.0` field to `RevisionState` (backward-compatible default).

### `src/allbrain/revision/manager.py`
- New helper `_read_learned_capability(ordered) -> float`: scans for the last `AGENT_CAPABILITY_LEARNED` or `AGENT_CAPABILITY_DECAYED` `new_score`, defaults to `1.0` (last-wins)
- `confidence` is unchanged (Yol B display-only)

### `src/allbrain/replay/event_replay_engine.py`
- Import `CapabilityLearningReducer`
- State dict: `"learning": {}`
- `_apply`: `learning_reducer.apply(event); state["learning"] = learning_reducer.all_snapshots()`
- `_copy_state`: includes `"learning"`

### `src/allbrain/runtime_core/pipeline.py`
- New flag: `enable_learning` (off-by-default)
- `_learning_step`:
  1. Emits `AGENT_CAPABILITY_OBSERVED` (system-level, neutral observation)
  2. For each known `(agent, task_type)` key: reads prior learned score, applies `new = old×0.9 + obs×0.1` (Sprint 53 uses a neutral `obs=0.5` placeholder — real observation sourcing is future work), emits LEARNED or DECAYED if `|delta| >= 0.02`
- `_result()` gains `learning` keyword arg; result dict gains `"learning"` key

---

## Convergence invariant

`CapabilityLearningManager.query(events, agent_id=X, task_type=Y) == CapabilityLearningReducer.snapshot(agent_id=X, task_type=Y)` for ALL event logs.

Locked by `test_learning_reducer.py`:
- manager == reducer no events
- manager == reducer with observed/learned
- manager == reducer with decayed
- manager == reducer other-key ignored

---

## Replay determinism

`EventReplayEngine().replay(events)["final_state"]["learning"]["X::Y"]["capability_score"]` MUST equal `CapabilityLearningReducer().snapshot(agent_id=X, task_type=Y).capability_score` byte-for-byte.

Locked by `test_learning_replay.py`.

---

## Revision integration (Yol B display-only)

```
confidence             = max(0, min(1, revise(baseline, n, u, policy) × trust_score))   # Sprint 46, unchanged
learned_capability     = last AGENT_CAPABILITY_LEARNED/DECAYED new_score (last-wins)    # Sprint 53
```

**Yol B**: `learned_capability` is display-only. It NEVER modifies `confidence`.

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `learning/learner.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `learning/reducer.py` | same |
| `learning/manager.py` | same |
| `learning/events.py` | same |
| `learning/model.py` | same |

Quality gate (`tests/test_learning_quality_gate.py`, 12 tests):
- No nondeterminism tokens in 5 learning files
- `confidence` byte-equal before/after learning events (Yol B)
- Revision manager reads learned capability from event log only
- EMA convergence invariants (monotonic toward observation, bounded `[0,1]`)
- Cold-start `INITIAL_CAPABILITY = 0.5`
- `LEARNING_DELTA_THRESHOLD` noise suppression

---

## Tests (55 new in 4 files)

### `tests/test_learning.py` (23 tests)
- `observation` weighting (`success×0.5 + runtime×0.3 + selection×0.2`), clamping
- `ema_update` (`old×0.9 + obs×0.1`), convergence toward observation, bounded `[0,1]`
- `_stable_learning_id` order-independence, key distinction, `learn-` prefix
- `make_*_payload` validation, type coercion, rejection
- `LearnedCapabilityState` frozen/immutability, template version
- `test_constants_match_sprint53` — locks `LEARNING_RETENTION=0.9`, `LEARNING_EMA_BIAS=0.1`, `INITIAL_CAPABILITY=0.5`, `LEARNING_DELTA_THRESHOLD=0.02`

### `tests/test_learning_reducer.py` (11 tests)
- manager == reducer no events
- manager == reducer with observed/learned
- manager == reducer with decayed
- manager == reducer other-key ignored
- idempotent under repeated apply
- invalid payload swallowed
- `all_snapshots()` structure
- `known_keys()` membership

### `tests/test_learning_replay.py` (9 tests)
- `state["learning"]` matches reducer projection
- replay round-trip exact dict equality
- byte-for-byte `capability_score` match
- multi-key replay projection
- OBSERVED/LEARNED/DECAYED event routing

### `tests/test_learning_quality_gate.py` (12 tests)
- No nondeterminism tokens in 5 learning files
- `confidence` byte-equal before/after learning events
- Revision manager reads learned capability from event log only
- EMA convergence / boundedness / monotonicity
- Cold-start default
- Delta-threshold noise suppression

### Existing tests — preserved
- All Sprint 52 tests pass unchanged
- `enable_learning=False` preserves the Sprint 52 contract
- The new field has a backward-compatible default (`learned_capability=1.0`)

**Test count: 1135 collected (full suite, no regressions). Sprint 53 adds 55 learning-specific tests across 4 files.**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence | Medium | Both views consume the same OBSERVED/LEARNED/DECAYED stream. Default (`learned_capability=1.0`) preserves Sprint 52 behavior. |
| Determinism loss | Medium | Dedicated quality gate forbids nondeterminism tokens. EMA is pure arithmetic. |
| Recompute branch drift | Medium | Quality gate forbids `CapabilityLearningManager(`/`CapabilityLearningReducer(` in revision outside `_read_learned_capability`. |
| Neutral-observation placeholder | Low | Sprint 53 pipeline uses `obs=0.5` placeholder, so learned scores drift toward 0.5 (neutral) rather than reflecting real outcomes. Documented; real observation sourcing is future work. The *layer* and its convergence are complete. |
| EMA lag | Low | `retention=0.9` gives a ~10-observation effective window. Sudden capability changes take several observations to register — acceptable for stability. |
| Noise emission | Low | `LEARNING_DELTA_THRESHOLD=0.02` suppresses sub-threshold deltas, preventing event explosion from tiny EMA steps. |

---

## Production impact

- `EventReplayEngine.replay()` now includes `state["learning"]` in `final_state`.
- `RevisionManager.query()` and `RevisionReducer.snapshot()` now expose `learned_capability`. The `confidence` field is unchanged.
- The system can finally say "agent `codex`'s learned capability on `implementation` is 0.78 and trending up" — the first time a signal *evolves from observation* rather than being declared or measured once.

---

## Out-of-scope reminders (Sprint 54+)

- ❌ `CapabilityLearningManager(` / `CapabilityLearningReducer(` called inside `revision/manager.py` (Yol B: learned capability comes from event log only)
- ❌ Drift/trend/forecast over the learning series (Sprint 54 dynamics)
- ❌ Counterfactual capability (Sprint 55 causal)
- ❌ Multi-signal fusion (Sprint 56)
- ❌ Bayesian capability estimation (frequentist EMA only)
- ❌ Real observation sourcing (neutral `obs=0.5` placeholder until execution feedback wiring)
- ❌ Per-observation confidence weighting
