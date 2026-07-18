# Sprint 73 — MCP Datetime Coercion + list_events Limit

## Goal

Harden the MCP tool surface against malformed and out-of-range inputs that were
causing `Input should be a valid datetime` and `Input should be less than or
equal to 500` validation errors on `list_events` and `save_event`/`work_summary`
style calls. Normalize naive datetimes to UTC, coerce string datetimes, and raise
the `list_events` `limit` ceiling from 500 to 1000.

## Architecture

`ListEventsInput` (`src/allbrain/models/schemas.py`) gained a pre-validation
coercion step so downstream code always receives tz-aware `datetime`:

- `_coerce_iso_datetime(value)` — accepts `datetime`, ISO-8601 strings
  (with or without `Z`/offset), and naive `datetime`; naive values are
  normalized to UTC via `value.replace(tzinfo=UTC)`.
- `field_validator("since", "until", mode="before")` applies the coercer, so a
  plain string like `"2026-07-17T00:00:00Z"` is accepted by the strict model.
- `limit` upper bound raised `500 -> 1000` (`Field(..., le=1000)`) to support
  larger client-side windows without paging.
- `WorkSummaryInput` received the same coercion for `since`/`until`.

The server `list_events` MCP tool already routed through
`ListEventsInput.model_validate`, so coercion was automatically applied once the
validator landed — no caller changes required.

## Files

| File | Change |
|------|--------|
| `src/allbrain/models/schemas.py` | `_coerce_iso_datetime` helper; `field_validator(mode="before")` on `ListEventsInput.since/until` and `WorkSummaryInput.since/until`; `limit` ceiling `500 -> 1000` |
| `tests/test_list_events_filters.py` | regression + e2e DB tests for coercion |
| `tests/test_work_summary_filters.py` | new (9 tests) |
| `tests/test_mcp_tool_contracts.py` | `limit` upper-bound assertion updated to `1000` |
| `tests/test_security.py` | `limit` upper-bound assertion updated to `1000` |

## Decisions

- Coerce rather than reject: clients (Kilo, Claude Code) frequently transmit
  string datetimes; rejecting them produced hard tool failures. Coercion keeps
  the same JSON schema (`str` in, `datetime` out) while being permissive.
- Normalize naive -> UTC centrally in the validator so no per-caller logic is
  needed and clock-skew/naive mixes cannot raise a raw `TypeError` (the helper
  swallows `TypeError` on mixed naive/aware and normalizes naive first).
- Raise the ceiling (not remove it): an unbounded `limit` is a denial-of-service
  vector on large event logs; 1000 is a safe large window that still bounds
  payload size.

## Verification

- `ruff format --check` / `ruff check`: clean
- Full suite: 2756 passed (stress excluded)
- Live (canlı) probe on 399-event 2026-07-17 window:
  - `list_events(since=..., until=..., limit=1000)` → `ok=true`, 399 events
  - `limit=5001` → correctly rejected (`le=1000`)
  - `since="yesterday"` → rejected (`Invalid isoformat string`)

## Commit

`a6d11a3 fix(schemas): Sprint 73 — MCP datetime coercion + list_events limit`
(Merged via PR #38 → `45c64fb`)
