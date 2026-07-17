# Sprint 46 — Evidence & Trust Layer

## Goal

Make evidence a first-class entity and represent source trust in the system. After Sprint 46, the revision layer applies `confidence × trust_score` (Yol B — post-multiply), so the system can finally say "I believe this, but the evidence's trustworthiness is low."

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
Revision (× trust_score)
```

## Scope

### In
1. New module `src/allbrain/evidence/` (6 files: `__init__`, `estimator`, `state`, `trust`, `decay`, `reducer`, `manager`)
2. Three new event types: `EVIDENCE_RECORDED`, `EVIDENCE_DECAYED`, `TRUST_UPDATED`
3. New pipeline steps: `_evidence_step` + `_trust_step` (off-by-default flags)
4. Revision integration (Yol B): `confidence × trust_score` applied post-`revise()` (Sprint 44's `revise()` signature unchanged)
5. Replay binding (`EvidenceReducer` in `EventReplayEngine`)
6. 32 tests across 5 files + quality gate

### Out of scope (Sprint 47+)
- Bayesian posterior updates on trust
- Per-agent trust policies
- Multi-source trust fusion
- Evidence decay driven by EVIDENCE_DECAYED events (Sprint 46: decay is replay-time only)
- Replacing `EVIDENCE_RECORDED` payload with composite schema

---

## Resolved design decisions (Yol B)

| Question | Decision |
|---|---|
| `revise()` signature | UNCHANGED — 4 args (confidence, contradiction_count, uncertainty, policy) |
| Trust application location | Manager + reducer snapshot + MCP output layer (Yol B: post-processing) |
| Trust default (no TRUST_UPDATED) | `1.0` (full confidence) — never `0.0` (avoids "bilinçsiz default çöküş") |
| EVIDENCE_DECAYED role | Metadata event — does NOT trigger computation. Decay is replay-time via `decay(event_distance)` |
| evidence_id source | Event emitter (pipeline / estimator) — reducer replay reads from payload |
| `evidence_weight` formula | `confidence × (1 - uncertainty)` — spec example `0.90 × 0.80 = 0.72` ✓ |
| `trust_score` formula | `mean(weights)` — empty list returns `1.0` |
| `decay` formula | `max(0, 1 - log(distance+1)/log(threshold+1))` — default threshold=1000 |

---

## Module changes

### `src/allbrain/evidence/`
**`estimator.py`**:
```python
def _stable_evidence_id(context_key, source_event_ids) -> str:
    """sha256("|".join(sorted(...)))[:12], prefix 'evidence-'"""
    
def evidence_weight(confidence, uncertainty) -> float:
    """confidence × (1 - uncertainty), clamped [0, 1]."""
    raw = confidence * (1.0 - uncertainty)
    return max(0.0, min(1.0, raw))
```

**`state.py`** — `EvidenceState` frozen dataclass:
```python
@dataclass(frozen=True)
class EvidenceState:
    context_key: str
    evidence_count: int
    average_weight: float
    trust_score: float
```

**`trust.py`**:
```python
def trust_score(weights) -> float:
    """mean(weights), clamped [0, 1]. Empty list returns 1.0."""
```

**`decay.py`**:
```python
def decay(event_distance, threshold=1000) -> float:
    """max(0, 1 - log(distance+1)/log(threshold+1)). No time."""
```

**`reducer.py`** — `EvidenceReducer`:
- Idempotent via `_seen_ids`
- `EVIDENCE_RECORDED`: append weight to per-context list
- `TRUST_UPDATED`: last-wins authoritative (per-context)
- `EVIDENCE_DECAYED`: no-op (metadata only, per Sprint 46 decision)
- All other event types: no-op

**`manager.py`** — `EvidenceManager.query`:
- `canonical_event_sort(events)`
- Counts EVIDENCE_RECORDED weights for context_key
- Last TRUST_UPDATED wins
- No recompute (Zorunlu)

### `src/allbrain/events/schemas.py`
Added: `EVIDENCE_RECORDED = "evidence_recorded"`, `EVIDENCE_DECAYED = "evidence_decayed"`, `TRUST_UPDATED = "trust_updated"` (EventType + SemanticEventType).

### `src/allbrain/revision/state.py`
Added `trust_score: float = 1.0` field to `RevisionState`.

### `src/allbrain/revision/manager.py` (Yol B)
- New helper `_read_trust_score(ordered, context_key) -> float`: scans for last TRUST_UPDATED matching context_key, defaults to `1.0`
- In `query()`: `new_confidence = max(0, min(1, revise(...) * trust_score))`
- `revise()` signature unchanged (4-arg, Sprint 44 contract preserved)

### `src/allbrain/revision/reducer.py` (Yol B)
- New state field: `_last_trust: dict[str, float] = {}`
- New branch in `apply()` for `TRUST_UPDATED`: updates `_last_trust[context_key]`
- In `snapshot()`: `confidence = max(0, min(1, revise(...) * trust_score))`
- `_state_to_dict()` includes `trust_score`

### `src/allbrain/replay/event_replay_engine.py`
- Import `EvidenceReducer`
- State dict: `"evidence": {}`
- Local var: `evidence_reducer = EvidenceReducer()` (17th param in `_apply`)
- `_copy_state`: includes `"evidence"`

### `src/allbrain/runtime_core/pipeline.py`
- New flags: `enable_evidence`, `enable_trust` (off-by-default)
- New `_evidence_step`: emits `EVIDENCE_RECORDED` with weight from `evidence_weight(belief.mean, min(1, contradiction_count * 0.1))`
- New `_trust_step`: emits `TRUST_UPDATED` with `trust_score([evidence_weight])`
- `_result()` signature gains `evidence` + `trust` keyword args
- Result dict gains `"evidence"` + `"trust"` keys

---

## Convergence invariant

`EvidenceManager.query(events, ctx=X) == EvidenceReducer.snapshot(ctx=X)` for ALL event logs.

Locked by `test_evidence_convergence.py`:
- No-events test (empty EvidenceState, trust=1.0 default)
- Evidence-only test (last trust defaults to 1.0)
- Last-trust-wins test
- Other-context-ignored test
- Replay round-trip exact dict equality

---

## Revision integration (Yol B)

```
new_confidence = max(0, min(1, revise(baseline, n, u, policy) × trust_score))
```

Spec example: `confidence=0.80, trust=0.60 → 0.80 × 0.60 = 0.48` ✓ (verified in `test_revision_confidence_multiplied_by_trust_yol_b`).

Trust score default is `1.0` — no recompute branch. The `_read_trust_score` helper only scans the event log for `TRUST_UPDATED` events. Quality gate `test_revision_trust_uses_event_log_only` enforces this: any forbidden call (`evidence_weight(`, `trust_score(`, `decay(`, `from allbrain.evidence`, `composite_uncertainty(`) outside the `_read_trust_score` helper is a test failure.

---

## Determinism contract

| File | Forbidden tokens |
|---|---|
| `evidence/estimator.py` | `uuid7`, `datetime.now`, `random.`, `time.time` |
| `evidence/reducer.py` | same |
| `evidence/manager.py` | same |
| `evidence/decay.py` | same |
| `evidence/trust.py` | same |
| `revision/manager.py` | `evidence_weight(`, `trust_score(`, `decay(`, `from allbrain.evidence`, `composite_uncertainty(` (outside `_read_trust_score`) |

Quality gate (`tests/test_evidence_quality_gate.py`) reads each determinism-critical file and asserts none of the four tokens appear.

---

## Tests (32 new in 5 files)

### `tests/test_evidence_estimator.py` (15 tests)
- `evidence_weight` basic formula (`0.90 × 0.80 = 0.72`), zero/full uncertainty, clamps
- `trust_score` mean, empty returns 1.0, single element
- `decay` zero distance = 1.0, monotonic decreasing, threshold boundary, custom threshold
- `_stable_evidence_id` order-independence, context distinction, evidence distinction, prefix `evidence-`

### `tests/test_evidence_convergence.py` (5 tests)
- manager == reducer no events, evidence only, trust last-wins, other-context ignored
- Replay round-trip exact dict equality

### `tests/test_evidence_determinism.py` (4 tests)
- Same events → same trust_score
- Reducer deterministic for canonical input
- Manager order-independent (canonical_event_sort)
- Reducer idempotent under repeated apply

### `tests/test_evidence_checkpoint.py` (5 tests)
- Last TRUST_UPDATED wins
- Trust default 1.0 when no TRUST_UPDATED
- Revision confidence multiplied by trust (Yol B: `0.80 × 0.60 = 0.48`)
- Revision no trust keeps baseline
- Manager == reducer agree with trust (canonical_event_sort)

### `tests/test_evidence_quality_gate.py` (3 tests)
- Forbidden tokens (`uuid7`, `datetime.now`, `random.`, `time.time`) absent from evidence module files
- Revision manager only reads trust from event log (no recompute)

### Existing tests — preserved
- All 435 Sprint 45 tests pass unchanged
- The trust multiplication is `1.0` default for logs without `TRUST_UPDATED`, so existing behavior is preserved when `enable_trust=False`

**Test count: 435 (Sprint 45) + 32 (new) = 467 (full regression passing in 496s)**

---

## Risk analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Convergence divergence | Medium | Both views consume same event stream. `trust_score` default 1.0 when no TRUST_UPDATED means behavior is preserved for older logs. Tests lock convergence for full EVIDENCE+TRUST log. |
| Recompute branch drift | Medium | Quality gate enforces `_read_trust_score` is the ONLY source of trust in revision module. Word-boundary regex avoids false positives from `_read_trust_score(` function name. |
| Determinism loss | Medium | Quality gate forbids `uuid7/datetime.now/random./time.time` in 5 evidence module files. `decay` uses `math.log` (pure function). |
| `EVIDENCE_DECAYED` ambiguity | Low | Documented as metadata-only. Reducer treats it as no-op. Future sprint can wire it. |

---

## Production impact

- `EventReplayEngine.replay()` now includes `state["evidence"]` in `final_state`. Replay-derived state and live-derived state share the same event-sourcing semantics.
- `RevisionManager.query()` and `RevisionReducer.snapshot()` now apply `confidence × trust_score` when `TRUST_UPDATED` events are in the log. Without `TRUST_UPDATED`, behavior is identical to Sprint 45.
- The system can finally say "I believe this (confidence X) but the evidence's trustworthiness is low (trust Y) → final confidence X × Y."

---

## Out-of-scope reminders (Sprint 47+)

- ❌ `trust_score()` called inside `revision/manager.py` (Yol B: trust comes from event log only)
- ❌ `decay()` driven by EVIDENCE_DECAYED events (Sprint 46: replay-time computation)
- ❌ Bayesian posterior updates on trust
- ❌ Per-agent / per-context-key policies
- ❌ Multi-source trust fusion