"""Domain module: events."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.models.schemas import (
    ListEventsInput,
    SaveEventInput,
    ToolResult,
    UserInputError,
)
from allbrain.security.rate_limit import check_tool_rate
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    maybe_auto_snapshot,
)
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.storage.database import open_session
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
    with open_session(context.repository.engine) as db:
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
        """Append an event to the shared event log.

        Args:
            type: Event type identifier.
            payload: Event data payload.
            file_path: Optional source file path.
            source: Event source label (default "agent").
            session_id: Optional session ID to associate.
            task_hint: Optional task hint string.
            importance: Optional importance rating.
            impact_score: Optional impact score.
            caused_by: Optional causal event reference.
            branch: Optional branch name.

        Returns:
            Tool result as a JSON-serializable dict.
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
        """Query and filter recorded events.

        Args:
            session_id: Optional session ID to filter by.
            type: Optional event type to filter by.
            limit: Maximum number of events to return (default 50).

        Returns:
            Tool result as a JSON-serializable dict.
        """
        result = list_events_impl(
            context,
            session_id=session_id,
            type=type,
            limit=limit,
        )
        return result.model_dump(mode="json")
