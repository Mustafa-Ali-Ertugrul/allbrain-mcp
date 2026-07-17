# Sprint 43 — Contradiction Event-Sourcing & Hardening

## Goal

Bring the `contradiction/` module to parity with the belief module:
event-sourced write-path, replay-bound reducer, deterministic IDs,
type-safe lifecycle binding, ≥10 tests + quality gate.

## Scope

### In

1. **Write-path (P0-B)** — `CONTRADICTION_DETECTED` EventType + SemanticEventType
   entry; pipeline `_contradiction_step` emits the event from
   `ContradictionDetector` output.
2. **Projection + reducer (P1-A)** — `ContradictionReducer` +
   `ContradictionManager` mirroring belief; `canonical_event_sort` over
   the event log; `sha256(sorted(evidence_event_ids))` deterministic ids;
   unknown-event no-op; replay engine binding via `_apply()`.
3. **Test suite (P0-A)** — `tests/test_contradiction_convergence.py` with
   13 tests + uuid7/now quality gate.
4. **Detector hardening (P1-B)** — lifecycle strings bound to `EventType`
   enum values; `frozenset` pairs (order-independent); named severity
   constants; `dedup_contradictions` over intent-pair signature.

### Out of scope (Sprint 44+)

- `CONTRADICTION_RESOLVED` event
- Severity recalibration (50/85/70 unchanged)
- Contradiction-driven belief revision (uncertainty ↑, prior ↓)
- Evidence decay
- Detector refactor to consume `EventRead` directly
- `LifecycleState` enum on `Intent`

---

## Critical design call: no recompute path

Contradiction has no "baseline+trailing" semantic — every
`CONTRADICTION_DETECTED` is a complete snapshot of contradictions at
that moment. The reducer is a pure projection over the
`CONTRADICTION_DETECTED` stream:

```
events → manager.query(events)  →  finds last CONTRADICTION_DETECTED → returns payload
events → reducer.apply(events)  →  stores last CONTRADICTION_DETECTED → snapshot() returns payload
```

Both views consume the same stream and emit the same per-context
snapshot. **Live detection runs in only two places, explicitly NOT
covered by the convergence invariant:**

- `pipeline._contradiction_step` — generates the `CONTRADICTION_DETECTED`
  event from the live intent stream (the write-path)
- `detect_contradictions_impl` MCP tool — ad-hoc on-demand detection

This eliminates the divergence class that bit belief in Sprint 42: if
both views consume only the same event log, divergence is impossible.

---

## File-by-file changes

### `src/allbrain/events/schemas.py`

- Added `CONTRADICTION_DETECTED = "contradiction_detected"` to `EventType`
- Added `EventType.CONTRADICTION_DETECTED` to `SemanticEventType`

### `src/allbrain/contradiction/detector.py` (refactored)

- `INCOMPATIBLE_LIFECYCLE` now a `frozenset[frozenset[str]]` built from
  `EventType.TASK_COMPLETED.value`, `EventType.TASK_BLOCKED.value`,
  `EventType.FAILURE.value` — order-independent, sourced from the enum.
- `frozenset({a, b}) in INCOMPATIBLE_LIFECYCLE` matches regardless of pair order.
- `_lifecycle_value(intent)` reads `intent.sub_goal` (matches
  `IntentExtractor._extract_one` exactly: "task_started", "task_completed",
  "task_blocked", "failure", "file_modified").
- `SEVERITY_GOAL_DIVERGENCE = 50`,
  `SEVERITY_LIFECYCLE_INCOMPATIBLE_SAME_GOAL = 85`,
  `SEVERITY_LIFECYCLE_INCOMPATIBLE_SHARED = 70` — named constants.
- `dedup_contradictions(contradictions)` — collapses duplicates over the
  same intent pair, keeping highest severity.
- `CONTRADICTION_TEMPLATE_VERSION = 1` — versioning constant for payloads.
- Public 7-key dict shape preserved byte-identical: `severity`,
  `severity_score`, `agents`, `related_files`, `a_goal`, `b_goal`,
  `evidence_intent_ids`. Severity scores 50/85/70 unchanged. **All 8
  existing `test_intent.py` contradiction tests pass unchanged.**

### `src/allbrain/contradiction/models.py` (new)

`ContradictionState` (Pydantic, mirrors `BeliefState`):
- `context_key: str` (non-empty validated)
- `contradictions: list[dict]`
- `severity_summary: dict[str, int]`
- `evidence_event_ids: list[str]`
- `analysis_id: str`
- `template_version: int = 1`

### `src/allbrain/contradiction/estimator.py` (new)

- `_stable_contradiction_id(evidence_event_ids)` — `sha256("|".join(sorted(...)))`,
  prefix `contradiction-`. Order-independent.
- `_contradiction_key_of(intent_ids)` — `"|".join(sorted(...))`. **Never
  `frozenset.__repr__()` (PYTHONHASHSEED-dependent, non-deterministic).**
- `list_detected_contradiction_contexts(events)` — set of context_keys
  that have at least one `CONTRADICTION_DETECTED` event.

### `src/allbrain/contradiction/reducer.py` (new)

`ContradictionReducer` mirrors `BeliefReducer`:
- `apply(event)` — idempotent via `_seen_ids`. Only processes
  `CONTRADICTION_DETECTED` events; all other types are no-op.
- `snapshot(context_key)` — returns the bucket as `ContradictionState`,
  or an empty `ContradictionState` if no event seen yet. **`analysis_id`
  is derived from `sorted(_seen_ids)` to match manager convergence.**
- `all_snapshots()` — dict of context_key → state dict, mirrors belief.
- `known_context_keys()` — set of seen context_keys.

### `src/allbrain/contradiction/manager.py` (new)

`ContradictionManager.query(events)`:
- `canonical_event_sort(events)` for order-independence.
- Finds LAST `CONTRADICTION_DETECTED` for the context_key; returns its
  payload as `ContradictionState`. **No recompute branch** (Zorunlu 1).
- `analysis_id` derived from `sorted(all_event_ids)` — the same source
  as the reducer's `_seen_ids`, so they always converge.

### `src/allbrain/contradiction/__init__.py`

Re-exports `ContradictionDetector`, `ContradictionManager`,
`ContradictionReducer`, `ContradictionState`, `INCOMPATIBLE_LIFECYCLE`,
severity constants, `CONTRADICTION_TEMPLATE_VERSION`, `dedup_contradictions`.

### `src/allbrain/replay/event_replay_engine.py`

- Import `ContradictionReducer`.
- State dict gains `"contradiction": {}`.
- `contradiction_reducer = ContradictionReducer()` local in `replay()`.
- `_apply()` signature gains `contradiction_reducer` parameter.
- Inside `_apply()`: `contradiction_reducer.apply(event)` then
  `state["contradiction"] = contradiction_reducer.all_snapshots()`.
- `_copy_state()` gains `"contradiction": dict(state.get("contradiction", {}))`.

### `src/allbrain/runtime_core/pipeline.py`

- New `_contradiction_step(bus, context, project_path, caused_by, limit)`:
  reads events via `repository.list_events`, extracts intents via
  `IntentExtractor`, runs `ContradictionDetector` + `dedup_contradictions`,
  publishes `CONTRADICTION_DETECTED` event with full payload.
- `enable_contradiction: bool = False` flag in `run()` (off by default).
- `contradiction_payload` propagated through `_result` and the
  `PIPELINE_RUN_COMPLETED` payload.

---

## Determinism contract

- `_stable_contradiction_id(evidence_ids)` = `sha256("|".join(sorted(ids)))[:12]`,
  prefix `contradiction-`. **Order-independent, process-independent.**
- `_contradiction_key_of(intent_ids)` = `"|".join(sorted(intent_ids))`.
  No `frozenset.__repr__` — `PYTHONHASHSEED` is process-random and would
  break replay repro.
- `analysis_id` derives from `sorted(all_event_ids)` in BOTH manager and
  reducer — convergence invariant `manager.query(events).analysis_id ==
  reducer.snapshot(context_key).analysis_id` holds for any event log.
- Quality gate: `estimator.py`, `reducer.py`, `manager.py` MUST NOT
  contain `uuid7()` or `datetime.now()`. Detector and pipeline
  (runtime write-path) are exempt.

---

## Tests (13 new in `tests/test_contradiction_convergence.py`)

| # | Test | Purpose |
|---|---|---|
| 1 | `test_contradiction_convergence_no_checkpoint` | Zorunlu 1 honest: no CONTRADICTION_DETECTED → both views return empty (no recompute) |
| 2 | `test_contradiction_convergence_with_checkpoint` | Both views return the same payload |
| 3 | `test_contradiction_intent_events_after_checkpoint_no_recompute` | Critical lock: intent events after checkpoint do NOT trigger recompute |
| 4 | `test_contradiction_order_independence` | `canonical_event_sort`: same analysis_id across orderings |
| 5 | `test_stable_contradiction_id` | Sorted inputs → same id; prefix `contradiction-` |
| 6 | `test_contradiction_key_of_deterministic` | Zorunlu 2: sorted join, no `frozenset.__repr__` |
| 7 | `test_contradiction_unknown_event_tolerance` | Reducer no-op on non-CONTRADICTION_DETECTED events |
| 8 | `test_contradiction_reducer_idempotency` | Re-applying same event_id is no-op |
| 9 | `test_contradiction_replay_round_trip_exact_equality` | Netleştirme 2: `final_state["contradiction"][context_key] == manager.query(events, context_key).model_dump()` |
| 10 | `test_contradiction_dedup` | Same intent pair → one entry, highest severity wins |
| 11 | `test_contradiction_lifecycle_bound_to_event_type` | Zorunlu 3: `INCOMPATIBLE_LIFECYCLE` values byte-identical to `IntentExtractor` sub_goal vocabulary (incl. `FAILURE.value = "failure"`, NOT `TASK_FAILED.value`) |
| 12 | `test_contradiction_detector_failure_lifecycle_matches_extractor` | Lock: contradiction over (task_completed, failure) detected when sub_goals match extractor's vocabulary |
| 13 | `test_contradiction_quality_gate_no_uuid7_or_now_in_determinism_path` | Quality gate: deterministic-only in estimator/reducer/manager |

All 13 tests pass. All 8 existing `test_intent.py` contradiction tests
pass unchanged (Zorunlu 3 byte-identical vocabulary). Full regression:
**378/378 tests** (365 pre-Sprint-43 + 13 new).

---

## Production impact

- `query_belief`-style MCP tools can now also expose contradiction state
  via `EventReplayEngine.replay()` or `ContradictionManager.query()`
  — both guaranteed to return the same snapshot for the same log.
- The pipeline emits `CONTRADICTION_DETECTED` snapshots when
  `enable_contradiction=True`. Replay-derived state and live-derived
  state now share the same event-sourcing semantics.
- The `contradiction_view` field in `IntentResumeEngine` and snapshot
  builder remains populated via live `ContradictionDetector().detect()`
  (the existing path, unchanged). Event-sourcing is additive.

---

## Out-of-scope reminders (deferred to Sprint 44+)

- `CONTRADICTION_RESOLVED` event (closed-lifecycle semantic)
- Severity recalibration (current 50/85/70 stays)
- Contradiction-driven belief revision (uncertainty ↑, prior ↓)
- Evidence decay
- LifecycleState enum on Intent
- Detector input refactor from Intent to EventRead
- Replay engine registry refactor (inline binding stays)