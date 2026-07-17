# Sprint 41 — Foundations Hardening

## Goal

Harden the event log foundation before Sprint 42 (Belief State). Three pillars:
1. `payload_version` migration with upcasters
2. Canonical UUIDv7-only ordering
3. Unknown-event-type tolerance
4. StateMachine event-id idempotency (B4)

Outcome: clean, forward-compatible event log that Sprint 42 (Belief State) can rely on without re-architecting.

## Locked Decisions

| # | Decision | Rationale |
|---|---|---|
| V1a | Explicit `payload_version: int = Field(default=1, ge=1)` on `EventRead` + `PayloadUpcaster` registry | Sprint 33 debt cleared, future-proof for v2 |
| V2a | `canonical_event_sort(events)` uses `(id,)` only | UUIDv7 is timestamp-monotonic; created_at is redundant |
| V4a | B4 event-id dedup in `core/state_machine.py` (Sprint 41) | StateMachine is foundational, not belief-specific |

## Architecture

```
src/allbrain/foundations/
├── __init__.py          # exports + __all__
├── versioning.py        # PayloadUpcaster + normalize_payload
├── ordering.py          # canonical_event_sort (UUIDv7-only primary)
└── tolerance.py         # KNOWN_EVENT_PREFIXES + is_known_event + partition_by_known
```

## Module Details

### `versioning.py` — Upcaster Registry

```python
class PayloadUpcaster:
    def __init__(self) -> None:
        self._upcasters: dict[tuple[int, int], Callable[[dict], dict]] = {}

    def register(self, from_version: int, to_version: int, fn: Callable[[dict], dict]) -> None:
        if to_version != from_version + 1:
            raise ValueError(...)
        self._upcasters[(from_version, to_version)] = fn

    def migrate(self, payload, *, from_version, to_version=PAYLOAD_CURRENT_VERSION) -> tuple[dict, int]:
        # chains upcasters v1→v2→v3...
        # raises if any step missing
        ...
```

`PAYLOAD_CURRENT_VERSION = 1`. Identity upcaster is implicit (v1→v1 is no-op).

### `ordering.py` — Canonical Sort

```python
def canonical_event_sort(events: list[EventRead]) -> list[EventRead]:
    return sorted(events, key=lambda event: event.id)
```

UUIDv7 timestamp-monotonic → id-only sort is fully deterministic. `created_at` becomes a sanity check, not a sort key.

### `tolerance.py` — Unknown Event Type Policy

```python
UNKNOWN_TYPE_POLICY = "skip_and_log"

KNOWN_EVENT_PREFIXES: frozenset[str] = frozenset({
    "world_", "counterfactual_", "scenario_", "foresight_",
    "meta_reasoning_", "decision_", "uncertainty_", "knowledge_gap_",
    "confidence_calibrated", "information_", "task_", "subtask_",
    "workflow_", "result_aggregated", "retry_scheduled", "agent_",
    "queue_", "worker_", "duplicate_detected", "idempotency_key_recorded",
    "lease_", "recovery_", "resource_closed", "snapshot_restored",
    "cluster_node_", "queue_backend_outage", "circuit_breaker_",
    "retry_attempted", "bulkhead_rejected", "team_", "collaboration_",
    "delegation_", "negotiation_", "proposal_", "vote_cast",
    "consensus_", "supervisor_intervention", "learning_cycle_",
    "recommendation_", "policy_update_", "organizational_pattern_",
    "governance_", "pipeline_", "objective_received",
    "selection_decision", "file_modified", "failure", "goal_set", "tool_call",
})

def is_known_event(event_type: str) -> bool:
    return any(event_type.startswith(prefix) for prefix in KNOWN_EVENT_PREFIXES)

def route_unknown_event(event_type: str, state: dict) -> None:
    state.setdefault("unknown_events", []).append({"type": event_type})

def partition_by_known(events, state=None) -> list:
    # filters unknown events; optionally routes them to state["unknown_events"]
    ...
```

## B4 Fix — StateMachine Idempotency

```python
class StateMachine:
    def __init__(self, state: ProjectState | None = None) -> None:
        self.state = state or ProjectState()
        self._applied_event_ids: set[str] = set()

    def apply(self, event: EventRead) -> None:
        if event.id in self._applied_event_ids:
            return
        self._applied_event_ids.add(event.id)
        # ... existing apply logic
```

`_record_tool_usage` additionally dedups by `event_id` for defense in depth.

## Replay Integration

`EventReplayEngine`:
- `_ordered()` now uses `canonical_event_sort` (id-only primary)
- `_apply()` routes unknown event types to `state["unknown_events"]` and increments `state["foundations"]["unknown_event_count"]`
- `_copy_state()` propagates `unknown_events` and `foundations` keys

Initial state:
```python
state = {
    "tasks": {}, "decisions": [], "failures": [], "collaboration": {},
    "organizational_learning": {}, "recommendations": {}, "policy_updates": {},
    "governance": {}, "runtime_core": {}, "world": {}, "counterfactual": {},
    "scenarios": {}, "foresight": {}, "reasoning": {}, "uncertainty": {},
    "knowledge_gaps": {}, "information_seeking": {}, "unknown_events": [],
    "foundations": {
        "ordering": "uuid7",
        "payload_version": 1,
        "unknown_event_count": 0,
    },
}
```

## Test Coverage (24 tests)

`tests/test_foundations.py` (18 tests):
1. `test_payload_version_default_is_1`
2. `test_upcaster_identity_v1_to_v1`
3. `test_upcaster_chain_v1_to_v3`
4. `test_upcaster_missing_step_raises`
5. `test_normalize_payload_v1_passthrough`
6. `test_canonical_ordering_uuid7_only`
7. `test_canonical_ordering_stable_under_created_at_collision`
8. `test_canonical_ordering_with_mixed_event_types`
9. `test_tolerance_unknown_world_event_skipped`
10. `test_tolerance_unknown_counterfactual_skipped`
11. `test_tolerance_unknown_scenario_skipped`
12. `test_tolerance_unknown_foresight_skipped`
13. `test_tolerance_unknown_meta_reasoning_skipped`
14. `test_tolerance_unknown_uncertainty_skipped`
15. `test_tolerance_unknown_information_seeking_skipped`
16. `test_replay_state_includes_foundations_meta`
17. `test_zero_behavior_change_golden`
18. `test_is_known_event_basic_check`

`tests/test_state_engine.py` (1 new test):
- `test_state_machine_idempotent_under_duplicated_events`

## Verification

- Targeted: `uv run pytest tests/test_foundations.py -v` → 18/18 ✅
- B4: `uv run pytest tests/test_state_engine.py -v` → 6/6 ✅
- Full regression: `uv run pytest -q` → 347/347 ✅ (329 + 18 new = zero behavior change)

## Files

**New (5):**
- `src/allbrain/foundations/__init__.py`
- `src/allbrain/foundations/versioning.py`
- `src/allbrain/foundations/ordering.py`
- `src/allbrain/foundations/tolerance.py`
- `tests/test_foundations.py`

**Changed (~5):**
- `src/allbrain/models/schemas.py` — `EventRead.payload_version`
- `src/allbrain/replay/event_replay_engine.py` — UUIDv7-only ordering + tolerance routing
- `src/allbrain/core/state_machine.py` — B4 event-id dedup
- `tests/test_state_engine.py` — B4 test
- `README.md` — Sprint 41 section

## Deferred (to Sprint 42+)

- **`PAYLOAD_VERSION_MIGRATED` event type** — informational event for explicit migration logging. Skipped (zero behavior change priority).
- **v2 event payload schemas** — Sprint 43+ when first evolution needed.
- **Per-projection `_skip_unknown` integration** — current projections already skip by prefix matching; explicit helper integration deferred to Sprint 42 when belief state adds new event types.
- **Upcaster logging** — `migrate()` raises on missing step (catches bugs early); defensive logging can be added in Sprint 42+.

## Sprint 42 (Belief State) Readiness

The foundations in this sprint prepare Sprint 42 by:
- Giving new `belief_*` event types an explicit `payload_version`
- Allowing Sprint 42 belief projections to skip unknown event types without crashing
- Ensuring StateMachine does not double-count duplicate `failure`/`tool_call` events during replay-based belief posterior updates
- Providing `canonical_event_sort` so belief posterior updates are deterministic
