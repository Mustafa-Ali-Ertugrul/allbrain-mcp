"""Shared helper functions used by tool implementation modules.

This module acts as a backward-compatible facade. The actual implementations
live in domain-specific submodules:

- ``_events`` — event cursor batching and task projection
- ``_snapshot`` — snapshot lease management and auto-snapshot trigger
- ``_tasks`` — task lookup, selection decisions, metrics, observability helpers
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from allbrain.models.schemas import UserInputError
from allbrain.server.context import BrainContext

# ── Re-exports from submodules (backward-compatible) ──────────────────────
from allbrain.server.tools._events import (  # noqa: F401
    iter_event_pages_through_cursor,
    iter_events_through_cursor,
    load_events_through_cursor,
    load_task_projection,
)
from allbrain.server.tools._snapshot import (  # noqa: F401
    _advisory_lock_key,
    _force_remove_lease,
    _snapshot_age_seconds,
    _snapshot_lease,
    _try_create_lease,
    maybe_auto_snapshot,
    snapshot_to_dict,
)
from allbrain.server.tools._tasks import (  # noqa: F401
    append_selection_decision,
    datetime_now_iso,
    filter_observability_events,
    get_task_or_raise,
    merge_agent_metrics,
    observability_project_and_limit,
    semantic_event_count,
)
from allbrain.storage.database import open_write_session

# ── Core tool utilities (session binding, audit, atomic write) ────────────

def bind_session_id(context: BrainContext, session_id: int | None) -> int:
    from allbrain.storage.database import open_session

    if session_id is not None:
        with open_session(context.repository.engine) as db:
            session = context.repository.get_session(db, session_id)
            if session is None:
                raise UserInputError("Invalid session")
            project = context.repository.get_project_by_path(context.project_path)
            if project is None or session.project_id != project.id:
                raise UserInputError("Invalid session")
        return session_id
    if context.active_session_id is None:
        raise UserInputError("No active session is available")
    return context.active_session_id


def audit_tool_call(
    context: BrainContext,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    session_id: int,
    _session: Any | None = None,
) -> None:
    if getattr(context, "central_audit_enabled", False):
        return
    context.repository.append_event(
        project_path=context.project_path,
        session_id=session_id,
        type="tool_call",
        source="allbrain",
        payload={
            "tool_name": tool_name,
            "tool_args": tool_args,
            "timestamp": datetime_now_iso(),
            "session_id": session_id,
        },
        _session=_session,
    )


@contextmanager
def atomic_write(context: BrainContext):
    """Open one write transaction for a logical tool operation."""
    with open_write_session(context.repository.engine) as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
