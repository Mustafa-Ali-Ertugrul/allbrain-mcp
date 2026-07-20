# Sprint 74 — list_events Cursor Pagination + Summary Mode

## Goal

Keep large `list_events` result sets within client payload limits. On
2026-07-17 a 399-event window produced a ~226 KB JSON blob that the Kilo client
truncated at its tool-output buffer. Sprint 74 adds opt-in cursor pagination and
an aggregate summary mode so clients can page through or summarize large windows
instead of fetching everything at once.

## Architecture

The repository already had cursor primitives (`list_events_after`,
`_cursor_stream_position`, `Event.stream_position`, `EventRead.stream_position`,
and `iter_event_pages_through_cursor` in `server/tools/_shared.py`). Sprint 74
exposed them through the `list_events` MCP tool via opt-in parameters.

- `ListEventsInput` gained `cursor: str | None` (a UUIDv7 event id anchor) and
  `summary: bool = False`. `_coerce_bool` was added so MCP clients that transmit
  booleans as JSON strings (`"true"`/`"false"`) are accepted under the strict
  model.
- `repository.list_events_paginated(...)` returns `(events, has_more)` using the
  `stream_position > cursor_position` filter and the classic `limit + 1` probe to
  detect a next page. `next_cursor` is `events[-1].id`.
- `repository.summarize_events(...)` pushes `GROUP BY` aggregation into SQLite
  (`by_type`, `by_agent`, `by_date`, first/last timestamps) so large windows
  return a few hundred bytes instead of every record.
- New wrappers `ListEventsPage { events, next_cursor, has_more, truncated }` and
  `ListEventsSummary { total, by_type, by_agent, by_date, first_event_at,
  last_event_at }` in `schemas.py`.
- `list_events_impl` dispatches by mode: `summary=True` → `ListEventsSummary`;
  `cursor is not None` → `ListEventsPage`; default → plain backward-compatible
  event list (no change for existing callers / SDK clients).

## Files

| File | Change |
|------|--------|
| `src/allbrain/models/schemas.py` | `_coerce_bool`; `ListEventsInput.cursor`/`summary`; `ListEventsPage`, `ListEventsSummary` |
| `src/allbrain/storage/repository.py` | `list_events_paginated`, `summarize_events` |
| `src/allbrain/server/tools/events.py` | `list_events_impl` opt-in dispatch; tool signature + docstring (`cursor`, `summary`) |
| `tests/test_list_events_pagination.py` | new (10 tests: pagination walk, invalid cursor, summary grouping) |
| `tests/test_mcp_tool_contracts.py` | +5 tool-level tests (default list / cursor page wrapper / summary dict / invalid cursor) |

## Decisions

- Backward-compatible opt-in (the "B" branch from planning): default
  `cursor=None, summary=False` keeps the exact old behavior (plain list), so no
  SDK or test breaks. Pagination/summary are only active when explicitly
  requested.
- Use `event.id` (UUIDv7) as the cursor anchor and validate it through the
  existing `_cursor_stream_position` helper, which raises `UserInputError` for
  unknown / wrong-project / no-stream-position cursors.
- Keep summary mode DB-side (`GROUP BY`) rather than loading records then
  aggregating in Python — essential for 5000+ event windows.

## Verification

- `ruff format --check` / `ruff check`: clean
- `pyright`: 0 errors
- Full suite: 2789 passed, 3 skipped
- Live probe (canlı) after MCP restart: `tools/list` shows `list_events` with
  `cursor=True`, `summary=True` → `SPRINT 74 LIVE OK`.

## Commit

`49832d4 Sprint 74: list_events cursor pagination + summary mode`
(Merged via PR #38 → `45c64fb`)
