# Sprint 49 — Arbitration & Consensus Layer

## Goal

Sprint 49 adds the multi-agent conflict-resolution layer. Where Sprint 46 modelled
trust and Sprint 48 modelled per-agent reputation, Sprint 49 lets agents *vote* on
a candidate decision and resolves the votes into a consensus winner. After this
sprint the system can finally say:

- "Three agents voted on candidate `task_42`: their weighted scores were 0.74,
  0.61, 0.55. The consensus winner is `task_42` with score 0.74 and agreement
  ratio 0.67."
- "I believe this (confidence X), the executing agent's reputation is 0.78
  (Sprint 48), and the team consensus on this decision is 0.74 (Sprint 49)."

The revision chain is extended (read-only, no recompute) with a per-context
consensus signal surfaced as `RevisionState.consensus_score`:

```
AGENT_CONSENSUS_REACHED → Revision (consensus_score, last-wins, default 1.0)
```

Consensus is **advisory metadata**: it records how the team agreed, it never
overrides the scheduler's actual assignment, and it is never recomputed inside
the replay path. The Sprint 46 `confidence` contract is preserved exactly.

## Architecture

```
Events
  ↓
AGENT_VOTE_CAST              (agent votes per candidate)
  ↓
AGENT_CONSENSUS_REACHED      (resolved winner + score + agreement)
  ↓
AGENT_ARBITRATION_DECISION   (final method + vote_count + candidate_scores)
  ↓
Revision (consensus_score)   (Sprint 49, last-wins, default 1.0)
  ↓
Snapshot (revision.consensus_score)
```

## Scope

### In

1. New module `src/allbrain/arbitration/` (6 files: `__init__`, `model`, `scorer`, `events`, `reducer`, `manager`)
2. Three new event types: `AGENT_VOTE_CAST`, `AGENT_CONSENSUS_REACHED`, `AGENT_ARBITRATION_DECISION`
3. New pipeline steps: `_vote_step` → `_consensus_step` → `_arbitration_step` (off-by-default flag)
4. Revision integration (Yol B display-only): `RevisionState` gains the `consensus_score` field, `confidence` is **unchanged**
5. Replay binding (`ArbitrationReducer` + `state["arbitration"]` projection in `EventReplayEngine`)
6. 31 tests across 4 files + quality gate

### Out of scope (Sprint 50+)

- Multi-round voting / iterative consensus (one round per pipeline run)
- Dissenting-vote rationale capture (votes carry no `reason` field)
- Reputation-weighted quorum rules (every vote is equally eligible; reputation enters the *score*, not the quorum)
- Real execution telemetry feeding vote confidence (Sprint 50)
- Tie-breaking policy beyond `max()` (deterministic but opaque — no documented tie rule)

---

## Resolved design decisions (Yol B display-only)

| Question | Decision |
|---|---|
| `revise()` signature | UNCHANGED — 4 args (Sprint 44 contract preserved) |
| `confidence` value | UNCHANGED — still `revise(...) × trust_score` (Sprint 46) |
| `consensus_score` source | Last `AGENT_CONSENSUS_REACHED` `score` (last-wins) |
| `consensus_score` default | `1.0` when no `AGENT_CONSENSUS_REACHED` events (Yol B: no data = full agreement assumed, never `0.0`) |
| Vote score formula | `confidence×0.4 + reputation×0.4 + calibrated_trust×0.2`, hard-clamped `[0, 1]` |
| Resolution methods | `weighted` (default) and `majority`; `ARBITRATION_METHODS = frozenset({"majority", "weighted"})` |
| Candidate id semantics | Opaque — the arbitration layer does not interpret `candidate_id` |
| Winner selection | `max(candidate_scores)` (deterministic; ties resolve to dict-insertion order) |
| `agreement_ratio` | `votes_for_winner / total_votes`; `0.0` when no winner |
| Pipeline default flag | `enable_arbitration=False` |
| Event source | Event log only (no recompute branch in revision layer) |

---

## Module changes

### `src/allbrain/arbitration/`

**`model.py`** — constants + frozen dataclasses:
```python
ARBITRATION_TEMPLATE_VERSION = 1
VOTE_CONFIDENCE_WEIGHT = 0.4
VOTE_REPUTATION_WEIGHT = 0.4
VOTE_TRUST_WEIGHT = 0.2
ARBITRATION_METHODS: frozenset[str] = frozenset({"majority", "weighted"})

@dataclass(frozen=True)
class VoteRecord:
    agent_id: str
    candidate_id: str
    confidence: float
    reputation: float
    calibrated_trust: float

@dataclass(frozen=True)
class ArbitrationState:
    context_key: str
    winner_candidate: str | None
    agreement_ratio: float
    arbitration_score: float
    vote_count: int
    method: str
    analysis_id: str
    template_version: int = ARBITRATION_TEMPLATE_VERSION
```

**`scorer.py`** — Pure functions:
```python
def _stable_arbitration_id(context_key, event_ids) -> str:
    """sha256(f"{context_key}:{'|'.join(sorted(event_ids))}")[:12], prefix 'arbitration-'"""

def vote_score(vote: VoteRecord) -> float:
    """confidence×W_c + reputation×W_r + calibrated_trust×W_t, clamped [0,1]."""

def candidate_scores(votes) -> dict[str, float]:
    """{candidate_id: mean(vote_score) over votes for that candidate}."""

def winner(candidate_scores) -> str | None:
    """max by score; None for empty dict."""

def agreement_ratio(votes, winner_candidate) -> float:
    """votes_for_winner / len(votes); 0.0 if no winner."""

def weighted_resolve(votes) -> tuple[str | None, float, float]:
    """(winner, score, agreement_ratio) via candidate_scores."""

def majority_resolve(votes) -> tuple[str | None, float, float]:
    """(winner, share, share) by raw vote count."""
```

**`events.py`** — Payload helpers (three payloads):
```python
VOTE_REQUIRED_KEYS = frozenset({"agent_id", "candidate_id", "confidence",
                                "reputation", "calibrated_trust", "context_key"})
CONSENSUS_REQUIRED_KEYS = frozenset({"context_key", "winner_candidate",
                                     "score", "agreement_ratio", "method"})
ARB_DECISION_REQUIRED_KEYS = frozenset({"context_key", "winner_candidate",
                                        "method", "vote_count", "candidate_scores"})

def validate_vote_payload(payload) -> None: ...
def validate_consensus_payload(payload) -> None: ...   # score/ratio in [0,1]
def validate_arb_decision_payload(payload) -> None: ... # vote_count >= 0 int
def make_vote_payload(*, agent_id, candidate_id, context_key,
                      confidence, reputation, calibrated_trust, ...) -> dict: ...
def make_consensus_payload(*, context_key, winner_candidate, score,
                           agreement_ratio, method, ...) -> dict: ...
def make_arb_decision_payload(*, context_key, winner_candidate, method,
                              vote_count, candidate_scores, ...) -> dict: ...
```

**`reducer.py`** — `ArbitrationReducer`:
- Idempotent via `_seen_ids`
- `AGENT_VOTE_CAST`: append `VoteRecord` to per-context vote list (validated)
- `AGENT_CONSENSUS_REACHED`: overwrite per-context consensus snapshot (last-wins)
- `AGENT_ARBITRATION_DECISION`: overwrite per-context decision record
- All other event types: no-op (unknown-event tolerance)
- `snapshot(context_key)`: prefers the recorded consensus; falls back to `weighted_resolve(votes)`; empty → winner `None`
- `all_snapshots()`, `known_context_keys()`

**`manager.py`** — `ArbitrationManager.query`:
- `canonical_event_sort(events)`
- Collects votes + consensus + method from the log for `context_key`
- No recompute (Zorunlu): mirrors reducer exactly

### `src/allbrain/events/schemas.py`
Added: `AGENT_VOTE_CAST = "agent_vote_cast"`, `AGENT_CONSENSUS_REACHED = "agent_consensus_reached"`, `AGENT_ARBITRATION_DECISION = "agent_arbitration_decision"` (EventType + SemanticEventType).

### `src/allbrain/revision/state.py`
Added `consensus_score: float = 1.0` field to `RevisionState` (backward-compatible default).

### `src/allbrain/revision/manager.py`
- New helper `_read_consensus_score(ordered) -> float`: scans for the last `AGENT_CONSENSUS_REACHED` `score`, defaults to `1.0` (no context filter — consensus is per-context but the revision helper reads the latest globally)
- `confidence` is unchanged (Yol B display-only)

### `src/allbrain/replay/event_replay_engine.py`
- Import `ArbitrationReducer`
- State dict: `"arbitration": {}`
- `_apply`: `arbitration_reducer.apply(event); state["arbitration"] = arbitration_reducer.all_snapshots()`
- `_copy_state`: includes `"arbitration"`

### `src/allbrain/runtime_core/pipeline.py`
- New flag: `enable_arbitration` (off-by-default)
- `_vote_step`: builds a vote from the scheduler `agent_id`, `belief_state.mean` (confidence), the agent's reputation (`ReputationManager.query`), and `trust_payload.calibrated_trust`; emits `AGENT_VOTE_CAST`
- `_consensus_step`: `weighted_resolve([vote])` → emits `AGENT_CONSENSUS_REACHED`
- `_arbitration_step`: emits `AGENT_ARBITRATION_DECISION` with the candidate scores
- `_result()` gains `consensus` + `arb_decision` keyword args
- Result dict gains `"vote"`, `"consensus"`, `"arbitration"` keys

---

## Convergence invariant

`ArbitrationManager.query(events, context_key=X) == ArbitrationReducer.snapshot(context_key=X)` for ALL event logs.

Locked by `test_arbitration_reducer.py`:
- manager == reducer no events
- manager == reducer with votes (weighted)
- manager == reducer consensus preferred over recompute
- manager == reducer other-context ignored

---

## Replay determinism

`EventReplayEngine().replay(events)["final_state"]["arbitration"][X]["arbitration_score"]` MUST equal `ArbitrationReducer().snapshot(context_key=X).arbitration_score` byte-for-byte.

Locked by `test_arbitration_replay.py`.

---

## Revision integration (Yol B display-only)

```
confidence        = max(0, min(1, revise(baseline, n, u, policy) × trust_score))   # Sprint 46, unchanged
consensus_score   = last AGENT_CONSENSUS_REACHED score (last-wins)                 # Sprint 49
```

**Yol B**: `consensus_score` is display-only. It NEVER modifies the `confidence` field. Verified by `test_does_not_change_confidence`: `confidence` is byte-equal before and after an `AGENT_CONSENSUS_REACHED` event is added.

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `arbitration/scorer.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `arbitration/reducer.py` | same |
| `arbitration/manager.py` | same |
| `arbitration/events.py` | same |
| `arbitration/model.py` | same |
| `revision/manager.py` | `ArbitrationManager(`, `ArbitrationReducer(` outside `_read_consensus_score` |

Quality gate (`tests/test_arbitration_quality_gate.py`):
- `test_no_nondeterminism` — forbidden tokens absent from 5 arbitration files
- `test_does_not_change_confidence` — Yol B display-only contract
- `test_no_recompute` — revision reads consensus from event log only

---

## Tests (31 new in 4 files)

### `tests/test_arbitration.py` (17 tests)
- `vote_score` weighting (`conf×0.4 + rep×0.4 + trust×0.2`), clamping
- `candidate_scores` bucketing and mean
- `winner` selection, empty dict → None
- `agreement_ratio` formula, no-winner → 0.0
- `weighted_resolve` full tuple
- `majority_resolve` count-based
- `make_*_payload` validation, type coercion, rejection of malformed payloads
- `VoteRecord` / `ArbitrationState` frozen/immutability, template version
- `ARBITRATION_METHODS` closed set

### `tests/test_arbitration_reducer.py` (8 tests)
- manager == reducer no events
- manager == reducer with votes (weighted)
- manager == reducer consensus preferred over recompute
- manager == reducer other-context ignored
- idempotent under repeated apply
- invalid vote payload swallowed
- `all_snapshots()` structure
- `known_context_keys()` membership

### `tests/test_arbitration_replay.py` (3 tests)
- `state["arbitration"]` matches reducer projection
- replay round-trip exact dict equality
- byte-for-byte `arbitration_score` match

### `tests/test_arbitration_quality_gate.py` (3 tests)
- No nondeterminism tokens in 5 arbitration files
- `confidence` byte-equal before/after consensus event
- Revision manager reads consensus from event log only

### Existing tests — preserved
- All Sprint 48 tests pass unchanged
- `enable_arbitration=False` preserves the Sprint 48 contract
- The new field has a backward-compatible default (`consensus_score=1.0`)

**Test count: 1135 collected (full suite, no regressions). Sprint 49 adds 31 arbitration-specific tests across 4 files.**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence | Medium | Both views consume the same event stream. Default (`consensus_score=1.0`) preserves Sprint 48 behavior. Tests lock convergence. |
| Recompute branch drift | Medium | Quality gate forbids `ArbitrationManager(`/`ArbitrationReducer(` in `revision/manager.py` outside `_read_consensus_score`. |
| Determinism loss | Medium | Quality gate forbids `uuid7/datetime.now/random./time.time` in 5 arbitration files. `_stable_arbitration_id` is sha256-based. |
| Single-vote triviality | Low | Pipeline currently casts one vote per run (the assigned agent). Multi-agent voting requires multi-agent execution wiring (future). The layer is structurally ready; only the vote *source* is single. |
| Tie ambiguity | Low | `max(dict, key=...)` is deterministic but insertion-order-dependent on ties. Documented as opaque; no business tie rule yet. |

---

## Production impact

- `EventReplayEngine.replay()` now includes `state["arbitration"]` in `final_state`.
- `RevisionManager.query()` and `RevisionReducer.snapshot()` now expose `consensus_score`. The `confidence` field is unchanged.
- The system can finally say "the assigned agent voted for this task; the weighted consensus score is 0.74" — the first time multiple signals (confidence, reputation, trust) are fused into a single arbitration number.

---

## Out-of-scope reminders (Sprint 50+)

- ❌ `ArbitrationManager(` / `ArbitrationReducer(` called inside `revision/manager.py` (Yol B: consensus comes from event log only)
- ❌ Multi-round / iterative consensus
- ❌ Dissenting-vote rationale capture
- ❌ Reputation-weighted quorum rules
- ❌ Documented tie-breaking policy
- ❌ Real multi-agent vote sourcing (currently one vote per run from the assignment)
