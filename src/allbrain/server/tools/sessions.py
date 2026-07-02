from __future__ import annotations

import logging
from collections import Counter
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Any

from allbrain.events import EventType
from allbrain.models.entities import utc_now
from allbrain.models.schemas import ToolResult, UserInputError
from allbrain.server.constants import EMPTY_SESSION_TTL_HOURS
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import audit_tool_call, bind_session_id

logger = logging.getLogger(__name__)


def build_session_report(
    context: BrainContext,
    *,
    limit: int = 150,
    include_empty: bool = False,
    detail_limit: int = 20,
) -> dict[str, Any]:
    if limit < 1 or limit > 5000:
        raise UserInputError("limit must be between 1 and 5000")
    if detail_limit < 0 or detail_limit > 500:
        raise UserInputError("detail_limit must be between 0 and 500")
    candidates = context.repository.list_sessions(project_path=context.project_path, limit=5000)
    if not include_empty:
        candidates = [session for session in candidates if session.status != "empty"]
    sessions = candidates[:limit]
    agents = Counter(session.agent_name for session in sessions)
    statuses = Counter(session.status for session in sessions)
    coverage = 0
    details: list[dict[str, Any]] = []
    previous_by_agent: dict[str, datetime] = {}
    rapid_reconnects = 0
    for session in reversed(sessions):
        previous = previous_by_agent.get(session.agent_name)
        if previous is not None and (session.started_at - previous).total_seconds() < 60:
            rapid_reconnects += 1
        previous_by_agent[session.agent_name] = session.started_at
    for session in sessions:
        events = context.repository.list_session_events(session.id or 0)
        if events:
            coverage += 1
        if len(details) >= detail_limit:
            continue
        summary_event = next(
            (event for event in reversed(events) if event.type == EventType.SESSION_SUMMARY.value),
            None,
        )
        details.append(
            {
                "session_id": session.id,
                "agent": session.agent_name,
                "client_name": session.client_name,
                "status": session.status,
                "started_at": session.started_at.isoformat(),
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "close_reason": session.close_reason,
                "event_count": len(events),
                "summary": summary_event.payload if summary_event is not None else None,
            }
        )
    return {
        "session_count": len(sessions),
        "eventful_sessions": coverage,
        "empty_event_sessions": len(sessions) - coverage,
        "event_coverage_rate": round(coverage / len(sessions), 6) if sessions else 0.0,
        "agents": dict(sorted(agents.items())),
        "statuses": dict(sorted(statuses.items())),
        "rapid_reconnects_under_60s": rapid_reconnects,
        "snapshot_count": context.repository.count_snapshots(project_path=context.project_path),
        "queue_states": context.repository.queue_state_counts(),
        "details": details,
    }


def summarize_sessions_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        bound_session_id = bind_session_id(context, None)
        limit = int(kwargs.get("limit", 150) or 150)
        include_empty = bool(kwargs.get("include_empty", False))
        detail_limit = int(kwargs.get("detail_limit", 20) or 0)
        report = build_session_report(
            context,
            limit=limit,
            include_empty=include_empty,
            detail_limit=detail_limit,
        )
        audit_tool_call(
            context,
            tool_name="summarize_sessions",
            tool_args={"limit": limit, "include_empty": include_empty, "detail_limit": detail_limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=report)
    except (UserInputError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def close_session_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    """Manually close an active session."""
    try:
        session_id = kwargs.get("session_id")
        if session_id is None:
            raise UserInputError("session_id is required")
        session_id = int(session_id)
        reason = str(kwargs.get("reason", "manual"))
        closed = context.repository.close_session(session_id, status="closed", reason=reason)
        if closed is None:
            return ToolResult(ok=False, error=f"Session {session_id} not found")
        with suppress(UserInputError):
            audit_tool_call(
                context,
                tool_name="close_session",
                tool_args={"session_id": session_id, "reason": reason},
                session_id=bind_session_id(context, None),
            )
        return ToolResult(
            ok=True,
            data={
                "session_id": closed.id,
                "status": closed.status,
                "ended_at": closed.ended_at.isoformat() if closed.ended_at else None,
            },
        )
    except (UserInputError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def cleanup_stale_sessions_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    """Reconcile stale sessions and delete old empty ones."""
    try:
        from allbrain.server.lifecycle import reconcile_stale_sessions

        reconciled = reconcile_stale_sessions(context)
        before = utc_now() - timedelta(hours=EMPTY_SESSION_TTL_HOURS)
        deleted = context.repository.cleanup_empty_sessions(project_path=context.project_path, before=before)
        if deleted:
            logger.info("Cleaned up %d empty session(s)", deleted)
        with suppress(UserInputError):
            audit_tool_call(
                context,
                tool_name="cleanup_stale_sessions",
                tool_args={"reconciled": len(reconciled), "deleted": deleted},
                session_id=bind_session_id(context, None),
            )
        return ToolResult(
            ok=True,
            data={
                "reconciled": len(reconciled),
                "deleted": deleted,
            },
        )
    except (UserInputError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def summarize_sessions(
        limit: int = 150,
        include_empty: bool = False,
        detail_limit: int = 20,
    ) -> dict[str, Any]:
        """Summarize recent agent sessions.

        Args:
            limit: Maximum number of sessions to include.
            include_empty: Whether to include empty sessions.
            detail_limit: Maximum number of session details to return.

        Returns:
            Tool result as a JSON-serializable dict.
        """
        return summarize_sessions_impl(
            context,
            limit=limit,
            include_empty=include_empty,
            detail_limit=detail_limit,
        ).model_dump(mode="json")

    @mcp.tool
    def close_session(
        session_id: int,
        reason: str = "manual",
    ) -> dict[str, Any]:
        """Close an active session.

        Args:
            session_id: ID of the session to close.
            reason: Reason for closing the session.

        Returns:
            Tool result as a JSON-serializable dict.
        """
        return close_session_impl(
            context,
            session_id=session_id,
            reason=reason,
        ).model_dump(mode="json")

    @mcp.tool
    def cleanup_stale_sessions() -> dict[str, Any]:
        """Clean up stale/expired sessions.

        Returns:
            Tool result as a JSON-serializable dict.
        """
        return cleanup_stale_sessions_impl(context).model_dump(mode="json")
