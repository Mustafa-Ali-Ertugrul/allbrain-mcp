"""Domain module: events."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.models.schemas import (
    ListEventsInput,
    SaveEventInput,
    ToolResult,
)
from allbrain.security.rate_limit import check_tool_rate
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
)
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.storage.database import open_write_session
from allbrain.storage.repository import event_to_read

logger = logging.getLogger(__name__)


@handle_tool_errors
def save_event_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    """Save event to project history with validation and rate limiting.

    Validates input, applies rate limits, appends event to storage with
    redaction/sanitization, and triggers auto-snapshot if configured.

    Returns:
        ToolResult with saved event data or error message.
    """
    check_tool_rate("save_event")
    data = SaveEventInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, data.session_id)
    with open_write_session(context.repository.engine) as db:
        event = context.repository.append_event(
            project_path=context.project_path,
            session_id=bound_session_id,
            type=data.type,
            source=data.source,
            payload=data.payload,
            file_path=data.file_path,
            agent_id=data.agent_id,
            task_hint=data.task_hint,
            importance=data.importance,
            impact_score=data.impact_score,
            caused_by=data.caused_by,
            branch=data.branch,
            _session=db,
        )
        audit_tool_call(
            context,
            tool_name="save_event",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
            _session=db,
        )
        db.commit()
        result_data = event_to_read(event).model_dump(mode="json")
    maybe_auto_snapshot(context, project_path=context.project_path)
    return ToolResult(ok=True, data=result_data)


@handle_tool_errors
def list_events_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    """List events from project history with optional filtering.

    Supports filtering by session_id and event type, with configurable limit.
    Rate limited to prevent abuse.

    Returns:
        ToolResult with list of events or error message.
    """
    check_tool_rate("list_events")
    data = ListEventsInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    events = context.repository.list_events(
        project_path=context.project_path,
        session_id=data.session_id,
        type=data.type,
        limit=data.limit,
    )
    audit_tool_call(
        context,
        tool_name="list_events",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data=[event.model_dump(mode="json") for event in events])


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def save_event(
        type: str,
        payload: dict[str, Any],
        file_path: str | None = None,
        source: str = "agent",
        session_id: int | None = None,
        task_hint: str | None = None,
        importance: int | None = None,
        impact_score: float | None = None,
        caused_by: str | None = None,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Append an event to the shared event log with optional metadata.

        Use this to record agent actions, decisions, and state changes. All events
        are append-only with stable UUIDv7 ordering, enabling deterministic replay.

        Side effects: Creates a new event in the SQLite event log. Triggers an
        automatic snapshot when the event threshold is reached. This is the primary
        write operation for the event-sourced architecture.

        Args:
            type: Event type identifier (e.g., "TASK_CREATED", "TASK_ASSIGNED",
                "TOOL_CALLED", "DECISION_MADE").
            payload: Event data as a JSON-serializable dict. Should contain the
                relevant state or information being recorded.
            file_path: Optional source file path (for code-related events).
            source: Event source label (default "agent"). Use "allbrain" for
                system-generated events, or the agent name for agent actions.
            session_id: Optional session ID to associate with (for multi-agent tracing).
            task_hint: Optional task hint string (helps with memory building).
            importance: Optional importance rating (1-5); higher values may trigger
                more frequent snapshots.
            impact_score: Optional impact score for decision events.
            caused_by: Optional causal event reference (creates event provenance).
            branch: Optional branch name (for git-based project tracking).

        Returns:
            The created event as a JSON-serializable dict with id, type, timestamp,
            payload, and all metadata fields.
        """
        result = save_event_impl(
            context,
            type=type,
            payload=payload,
            file_path=file_path,
            source=source,
            session_id=session_id,
            task_hint=task_hint,
            importance=importance,
            impact_score=impact_score,
            caused_by=caused_by,
            branch=branch,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def list_events(
        session_id: int | None = None,
        type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query and filter recorded events from the append-only event log.

        Use this to inspect the history of agent actions and system state changes.
        Events are ordered by the database-authoritative stream position for
        consistent replay.

        Side effects: Read-only operation; no data is modified.

        Args:
            session_id: Optional session ID to filter by (useful for multi-agent
                debugging and isolation).
            type: Optional event type to filter by (e.g., "TASK_CREATED",
                "TASK_ASSIGNED", "TOOL_CALLED").
            limit: Maximum number of events to return (default 50). Increase for
                broader history inspection.

        Returns:
            List of events as JSON-serializable dicts, each containing id, type,
            timestamp, source, payload, and optional metadata fields.
        """
        result = list_events_impl(
            context,
            session_id=session_id,
            type=type,
            limit=limit,
        )
        return result.model_dump(mode="json")
