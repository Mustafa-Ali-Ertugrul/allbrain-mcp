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

# ── Deprecated re-exports (v0.3.0 removal) ────────────────────────────────
# Symbols that now live in domain submodules. Importing them from this facade
# still works but emits a DeprecationWarning so callers migrate before v0.3.0.
_DEPRECATED_REEXPORTS: dict[str, str] = {
    "iter_event_pages_through_cursor": "allbrain.server.tools._events",
    "iter_events_through_cursor": "allbrain.server.tools._events",
    "load_events_through_cursor": "allbrain.server.tools._events",
    "load_task_projection": "allbrain.server.tools._events",
    "maybe_auto_snapshot": "allbrain.server.tools._snapshot",
    "snapshot_to_dict": "allbrain.server.tools._snapshot",
    "append_selection_decision": "allbrain.server.tools._tasks",
    "datetime_now_iso": "allbrain.server.tools._tasks",
    "filter_observability_events": "allbrain.server.tools._tasks",
    "get_task_or_raise": "allbrain.server.tools._tasks",
    "merge_agent_metrics": "allbrain.server.tools._tasks",
    "observability_project_and_limit": "allbrain.server.tools._tasks",
    "semantic_event_count": "allbrain.server.tools._tasks",
}

import warnings  # noqa: E402

__all__ = [
    "bind_session_id",
    "audit_tool_call",
    "atomic_write",
    "open_write_session",
    *list(_DEPRECATED_REEXPORTS),
]


def __getattr__(name: str):  # noqa: N807
    """Lazily resolve deprecated re-exports with a warning."""
    target = _DEPRECATED_REEXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    warnings.warn(
        f"Importing {name!r} from 'allbrain.server.tools._shared' is deprecated; "
        f"import it from '{target}' instead. This re-export will be removed in v0.3.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    import importlib

    return getattr(importlib.import_module(target), name)


from allbrain.storage.database import open_write_session  # noqa: E402

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
    from allbrain.server.tools._tasks import datetime_now_iso

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
