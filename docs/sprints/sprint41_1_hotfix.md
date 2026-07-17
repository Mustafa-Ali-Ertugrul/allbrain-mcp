# Sprint 41.1 — Foundations Hardening Hotfix

## Goal

Close three blockers left open by Sprint 41 (031a87b). Sprint 41 added the `foundations/` module and the B4 idempotency fix, but three foundations were not actually wired into the live paths. This sprint wires them.

| # | Blocker | Fix |
|---|---|---|
| B1 | Storage path `created_at`-dominant ordering persists; only replay engine used id-only | `list_events()` becomes id-only (F1) |
| B2 | `payload_version` exists only on `EventRead`; not persisted, not stamped, not normalized on read | `Event.payload_version` field, `append_event` stamps, `event_to_read` normalizes via `migrate()` (F2) |
| B3 | `StateMachine.apply` crashes on unknown event types (replay engine filtered, core did not) | `try/except ValueError` no-op, mirrors replay engine (F3) |

## Locked Decisions

| # | Decision |
|---|---|
| F1 | Storage id-only primary sort, "latest N ascending" semantics preserved (`order_by(id.desc())` + `sorted(key=event.id)`) |
| F2 | Persist + normalize: `Event.payload_version: int = Field(default=1)`, `append_event` stamps `current_payload_version()`, `event_to_read` runs `migrate()` and reflects the achieved version on `EventRead.payload_version` |
| F3 | Core reducer unknown-tolerant: `try/except ValueError` no-op. Dedup + `last_event_id` advance stay before the try |

### Sprint 41.1 Additional Mandates (from review)

1. **Upgrade-path safety**: `ensure_event_payload_version_column` is called from `BrainRepository.__init__` (idempotent). Every brain-DB open path runs the migration; existing `~/.allbrain/allbrain.db` upgrades without ORM-level `no such column` crash. `getattr(event, "payload_version", 1)` does NOT save us — the ORM emits `SELECT event.id, ..., event.payload_version FROM event`, which fails before row materialization.
2. **`EventRead.payload_version` reflects the achieved version**: When an upcaster fires (e.g. v1→v2), the read model sees `payload_version=2` and the current-shape payload. Consumers that branch on `payload_version` get the right value.
3. **DDL via `engine.begin()` + `exec_driver_sql`**: Cleaner transactional DDL than `db.exec + commit`.
4. **No event-shape snapshot affected**: `grep -rn "model_dump|payload_version" tests/test_server.py tests/test_cli.py tests/test_snapshot.py` returned no full-EventRead assertions. Only sub-key reads like `.payload["tool_name"]`. New `payload_version` field is safe for existing API consumers.

## Architecture Changes

### `src/allbrain/models/entities.py` — Event
```python
class Event(SQLModel, table=True):
    ...
    payload_version: int = Field(default=1, ge=1)
```

### `src/allbrain/storage/database.py` — Migration helper
```python
def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
    ensure_event_payload_version_column(engine)


def ensure_event_payload_version_column(engine: Engine) -> None:
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(event)").fetchall()
        column_names = [row[1] for row in rows]
        if "payload_version" not in column_names:
            conn.exec_driver_sql(
                "ALTER TABLE event ADD COLUMN payload_version INTEGER NOT NULL DEFAULT 1"
            )
```

### `src/allbrain/storage/repository.py`
- `BrainRepository.__init__` calls `ensure_event_payload_version_column(engine)` (idempotent — every brain-DB open path)
- `list_events`: `order_by(col(Event.id).desc()).limit(limit)` + `sorted(key=event.id)` (F1)
- `append_event`: `payload_version=current_payload_version()` (F2 stamp)
- `event_to_read`: `get_default_upcaster().migrate(...)`, sets `payload_version=achieved_version` (F2 + achieved-version)

### `src/allbrain/core/state_machine.py`
```python
def apply(self, event: EventRead) -> None:
    if event.id in self._applied_event_ids:
        return
    self._applied_event_ids.add(event.id)
    self.state.last_event_id = event.id
    try:
        event_type = EventType(event.type)
    except ValueError:
        return
    # ... existing switch
```

### `src/allbrain/foundations/versioning.py` — Dynamic current version
`PAYLOAD_CURRENT_VERSION = 1` constant removed. Replaced with:
- `PayloadUpcaster._max_version` (tracks the highest registered upcaster target)
- `current_payload_version()` — returns the dynamic max
- `migrate()` defaults `to_version` to `current_payload_version()` if `None`
- `unregister(from, to)` resets max accordingly

This makes `current_payload_version()` advance from 1 → 2 when `register(1, 2, ...)` is called, and back to 1 on `unregister(1, 2)`. Test isolation is preserved.

## Test Coverage (5 new tests)

`tests/test_foundations.py`:
- **`test_list_events_ordered_by_id_not_created_at`**: insert events, manually set `created_at` to reverse-id order, assert `list_events` returns id-ascending
- **`test_payload_version_persisted_and_stamped`**: `append_event` round-trips `payload_version` through both raw row and `EventRead`
- **`test_upcaster_fires_on_read`**: register v1→v2 upcaster, write a v1 row, assert `event_to_read` returns v2-shaped payload and `payload_version == 2` (the achieved version). Unregisters in teardown.

`tests/test_state_engine.py`:
- **`test_state_machine_tolerates_unknown_event_type`**: `EventRead(type="future_unknown_event", ...)` → `StateEngine().build_state(...)` does not raise; only `last_event_id` advances

`tests/test_storage.py`:
- **`test_payload_version_column_backfilled_on_old_schema`**: simulates a pre-Sprint-41 DB (raw DDL with no `payload_version` column), inserts a row, calls `ensure_event_payload_version_column` twice (idempotency), then `BrainRepository.list_events` does not raise `OperationalError` and returns the row with `payload_version=1` (default) and `payload_version=current_payload_version()` on read (post-migration).

## Event-Shape Snapshot Audit

```
grep -rn "model_dump|payload_version" tests/test_server.py tests/test_cli.py tests/test_snapshot.py
```
- No `model_dump()` full-EventRead assertions
- No `payload_version` checks outside `tests/test_foundations.py`
- `list_events` uses are all sub-key reads (`.payload["tool_name"]`, `.payload["index"]`)

**No event-shape snapshot affected.** This sprint's API surface change is purely additive.

## Verification

- Targeted: `uv run pytest tests/test_foundations.py tests/test_state_engine.py tests/test_storage.py -v` → 34/34 ✅
- Full regression: `uv run pytest -q` → 353/353 ✅ (348 baseline + 5 new)
- Zero behavior change for callers that don't branch on `payload_version`

## Files

**Changed (~7):**
- `src/allbrain/models/entities.py` — `Event.payload_version`
- `src/allbrain/storage/database.py` — `init_db` + `ensure_event_payload_version_column` helper
- `src/allbrain/storage/repository.py` — `BrainRepository.__init__` (ensure), `list_events` (id-only), `append_event` (stamp), `event_to_read` (normalize + achieved-version)
- `src/allbrain/storage/__init__.py` — export `ensure_event_payload_version_column`
- `src/allbrain/foundations/versioning.py` — `current_payload_version()` + `unregister` + dynamic max
- `src/allbrain/foundations/__init__.py` — export `current_payload_version`
- `src/allbrain/core/state_machine.py` — `apply` try/except

**Test changes (~3):**
- `tests/test_foundations.py` — 3 new tests + import updates
- `tests/test_state_engine.py` — 1 new test
- `tests/test_storage.py` — 1 new test

## Acceptance Checklist

- [x] `list_events()` and `list_events_after()` both order by UUIDv7 id only — single canonical order across storage and replay paths.
- [x] `payload_version` persisted on `Event`, stamped on write, normalized on read; a registered upcaster actually fires (proven by `test_upcaster_fires_on_read`).
- [x] `StateMachine.apply` is forward-compatible: unknown/future type is a no-op, not a crash, on the core state-build path.
- [x] Full suite green; golden zero-behavior-change preserved.
- [x] `BrainRepository.__init__` runs `ensure_event_payload_version_column` on every brain-DB open — upgrade-path safety proven by `test_payload_version_column_backfilled_on_old_schema`.
- [x] `EventRead.payload_version` reflects the achieved (post-migration) version, not the stored version.

## Deferral (unchanged, still honest)

- Distributed multi-node ordering (HLC / monotonic sequence) — UUIDv7 timestamp bits are still wall-clock-derived. Cross-node clock skew not solved. **No distributed-safe ordering claim.**
- `PAYLOAD_VERSION_MIGRATED` event + concrete v2 schemas — deferred until a real payload actually changes.

## Sprint 42 (Belief State) Readiness

The three blockers closed here mean Sprint 42 can:
- Rely on a single canonical event order (storage + replay)
- Persist `belief_*` event payloads with explicit `payload_version`
- Have belief projections and core state-build both tolerate unknown event types
- Trust that upgrade from a pre-Sprint-41 DB does not crash
