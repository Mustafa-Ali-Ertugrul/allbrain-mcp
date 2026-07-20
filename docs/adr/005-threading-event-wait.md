# ADR-005: time.sleep → threading.Event().wait()

## Status: Accepted (v0.2.4)

## Context

Database retry loops used `time.sleep()` for backoff. This blocks the
thread unconditionally, preventing graceful shutdown during retry windows.

## Alternatives Considered

1. **Keep time.sleep:** Simple, well-understood — Rejected.
   Uninterruptible during shutdown; thread appears hung.
2. **threading.Event().wait():** Interruptible sleep — Selected.
3. **asyncio.sleep:** Requires async context — Rejected.
   Storage layer is synchronous (SQLAlchemy sync engine).

## Decision

Replace `time.sleep(delay)` with `threading.Event().wait(timeout=delay)`
in database retry loops. The event is set during shutdown to interrupt
the wait.

## Consequences

- Graceful shutdown improved: retry loops abort within `delay` seconds
- Slight complexity increase (event object lifecycle)
- Reverted to honest `time.sleep` after code review identified that
  interruptibility was not actually needed in the specific hot path;
  kept for general principle documentation
