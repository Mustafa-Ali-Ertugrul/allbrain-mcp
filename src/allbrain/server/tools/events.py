"""Domain module: events."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.models.schemas import (
    ListEventsInput,
    ListEventsPage,
    ListEventsSummary,
    SaveEventInput,
    ToolResult,
)
from allbrain.security.quarantine import (
    compute_promoted_set,
    filter_quarantined,
    mark_quarantined,
    scan_prompt_injection,
)
from allbrain.security.rate_limit import check_tool_rate
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
)
from allbrain.server.tools._snapshot import maybe_auto_snapshot
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.storage.database import open_write_session
from allbrain.storage.repository import event_to_read

logger = logging.getLogger(__name__)


@handle_tool_errors
def save_event_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    """Save event to project history with validation and rate limiting.

    Validates input, applies rate limits, scans for prompt injection
    (quarantining suspicious payloads), appends event to storage with
    redaction/sanitization, and triggers auto-snapshot if configured.

    Returns:
        ToolResult with saved event data or error message.
    """
    check_tool_rate("save_event")

    # §1 Memory poisoning defense: scan RAW payload for prompt injection
    # BEFORE validation/sanitization, so injection patterns aren't masked first
    raw_payload = kwargs.get("payload", {})
    injection_matches = scan_prompt_injection(raw_payload)
    if injection_matches:
        logger.warning(
            "security_event",
            extra={
                "event": "prompt_injection_detected",
                "matched_patterns": injection_matches,
                "event_type": kwargs.get("type", "unknown"),
                "action": "quarantined",
            },
        )
        kwargs["payload"] = mark_quarantined(raw_payload)

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

    Supports filtering by session_id, type, agent_id, branch, since, until,
    and limit. Cursor pagination (``cursor``) and aggregate summary mode
    (``summary``) keep large result sets within client payload limits.
    Rate limited to prevent abuse.

    Returns:
        ToolResult whose data is a ListEventsPage. The default window (no
        cursor) is also served through the paginated path and is truncated
        (``truncated=True`` + ``next_cursor``) when it exceeds the requested
        limit, so very large windows never overflow the client. When
        ``summary`` is true the data is a ListEventsSummary instead.
    """
    check_tool_rate("list_events")
    data = ListEventsInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)

    # §1 Security: when include_quarantined=False (default), we need to
    # know which events have been promoted so we can still show them.
    promoted_ids: set[str] | None = None
    if not data.include_quarantined:
        all_raw = context.repository.list_events(
            project_path=context.project_path,
            type="quarantine_lifted",
            limit=10000,
        )
        promoted_ids = {e.caused_by for e in all_raw if e.caused_by}

    if data.summary:
        summary = context.repository.summarize_events(
            project_path=context.project_path,
            session_id=data.session_id,
            agent_id=data.agent_id,
            type=data.type,
            branch=data.branch,
            since=data.since,
            until=data.until,
        )
        result_data: Any = ListEventsSummary.model_validate(summary).model_dump(mode="json")
    elif data.cursor is not None:
        events, has_more = context.repository.list_events_paginated(
            project_path=context.project_path,
            session_id=data.session_id,
            agent_id=data.agent_id,
            type=data.type,
            branch=data.branch,
            since=data.since,
            until=data.until,
            cursor=data.cursor,
            limit=data.limit,
        )
        if not data.include_quarantined and promoted_ids is not None:
            events = [e for e in events if not e.quarantined or e.id in promoted_ids]
        next_cursor = events[-1].id if (has_more and events) else None
        page = ListEventsPage(
            events=events,
            next_cursor=next_cursor,
            has_more=has_more,
            truncated=has_more,
        )
        result_data = page.model_dump(mode="json")
    else:
        # Backward-compatible default still uses the plain event list, but is
        # now served through the paginated path so an over-large window is
        # truncated (with next_cursor) instead of overflowing the client.
        events, has_more = context.repository.list_events_paginated(
            project_path=context.project_path,
            session_id=data.session_id,
            agent_id=data.agent_id,
            type=data.type,
            branch=data.branch,
            since=data.since,
            until=data.until,
            cursor=None,
            limit=data.limit,
        )
        if not data.include_quarantined and promoted_ids is not None:
            events = [e for e in events if not e.quarantined or e.id in promoted_ids]
        next_cursor = events[-1].id if (has_more and events) else None
        page = ListEventsPage(
            events=events,
            next_cursor=next_cursor,
            has_more=has_more,
            truncated=has_more,
        )
        result_data = page.model_dump(mode="json")

    audit_tool_call(
        context,
        tool_name="list_events",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data=result_data)


def _register_save_event(mcp, context: BrainContext) -> None:
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

        Records agent actions, decisions, and state changes. All events are
        append-only with stable UUIDv7 ordering for deterministic replay.

        Side effects: Creates a new event in the SQLite event log. Triggers
        an automatic snapshot when the event threshold is reached.

        Args:
            type: Event type identifier in snake_case (e.g., "task_created",
                "task_assigned", "tool_call", "file_modified"). SCREAMING_SNAKE
                aliases such as "TASK_CREATED" are also accepted.
            payload: Event data as a JSON-serializable dict.
            file_path: Optional source file path (for code-related events).
            source: Event source label (default "agent").
            session_id: Optional session ID to associate with.
            task_hint: Optional task hint string (helps with memory building).
            importance: Optional importance rating (1-5).
            impact_score: Optional impact score for decision events.
            caused_by: Optional causal event reference.
            branch: Optional branch name (for git-based project tracking).

        Returns:
            The created event as a JSON-serializable dict.
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


def _register_list_events(mcp, context: BrainContext) -> None:
    @mcp.tool
    def list_events(
        session_id: int | None = None,
        type: str | None = None,
        agent_id: str | None = None,
        branch: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
        summary: bool = False,
        include_quarantined: bool = False,
    ) -> dict[str, Any]:
        """Query and filter recorded events from the append-only event log.

        Use this to inspect the history of agent actions and system state changes.
        Events are ordered by the database-authoritative stream position for
        consistent replay.

        Side effects: Read-only operation; no data is modified.

        Args:
            session_id: Optional session ID to filter by (useful for multi-agent
                debugging and isolation).
            type: Optional event type filter in snake_case (e.g., "task_created",
                "task_assigned", "tool_call"). SCREAMING_SNAKE aliases accepted.
            agent_id: Optional agent id filter (same length rules as save_event).
            branch: Optional branch name filter.
            since: Optional ISO-8601 lower bound on event created_at (inclusive).
            until: Optional ISO-8601 upper bound on event created_at (inclusive).
            limit: Maximum number of events to return (default 50, maximum 500).
            cursor: Optional pagination cursor (from previous next_cursor).
            summary: When true, return aggregate counts instead of event records.
            include_quarantined: When true, include events flagged as
                quarantined for prompt injection (default False — quarantined
                events are excluded from normal context for safety).

        Returns:
            A page object with ``events``, ``next_cursor``, ``has_more``,
            and ``truncated``. When ``summary`` is true, returns aggregate
            counts instead of full event records.
        """
        result = list_events_impl(
            context,
            session_id=session_id,
            type=type,
            agent_id=agent_id,
            branch=branch,
            since=since,
            until=until,
            limit=limit,
            cursor=cursor,
            summary=summary,
            include_quarantined=include_quarantined,
        )
        return result.model_dump(mode="json")


def _register_review_quarantined(mcp, context: BrainContext) -> None:
    @mcp.tool
    def review_quarantined(
        limit: int = 50,
    ) -> dict[str, Any]:
        """List events that were quarantined for prompt injection detection.

        Returns events whose payload triggered prompt injection patterns.
        These events are stored but excluded from default ``list_events`` and
        ``resume_project`` output for safety. Use this tool to audit
        quarantined content.

        Side effects: Read-only operation.

        Args:
            limit: Maximum number of quarantined events to return (default 50).

        Returns:
            A list of quarantined event records with their quarantine status.
        """
        check_tool_rate("list_events")
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(
            project_path=context.project_path,
            limit=limit * 5,
        )
        promoted_events = context.repository.list_events(
            project_path=context.project_path,
            type="quarantine_lifted",
            limit=10000,
        )
        promoted_ids = {e.caused_by for e in promoted_events if e.caused_by}
        quarantined = [
            e for e in events
            if getattr(e, "quarantined", False)
        ]
        for e in quarantined:
            e.quarantined = e.id not in promoted_ids
        audit_tool_call(
            context,
            tool_name="review_quarantined",
            tool_args={"limit": limit},
            session_id=bound_session_id,
        )
        return {"ok": True, "data": [e.model_dump(mode="json") for e in quarantined[:limit]]}


def _register_promote_event(mcp, context: BrainContext) -> None:
    @mcp.tool
    def promote_event(
        event_id: str,
    ) -> dict[str, Any]:
        """Promote a quarantined event by appending a quarantine_lifted event.

        This does NOT mutate the original event. Instead, a new
        ``quarantine_lifted`` event is appended to the event log with
        ``caused_by`` pointing to the quarantined event. After promotion,
        the event reappears in default ``list_events`` and ``resume_project``
        output.

        Side effects: Appends a new event to the SQLite event log.

        Args:
            event_id: The ID of the quarantined event to promote.

        Returns:
            The created quarantine_lifted event record.
        """
        check_tool_rate("save_event")
        bound_session_id = bind_session_id(context, None)
        from allbrain.events.schemas import EventType

        with open_write_session(context.repository.engine) as db:
            event = context.repository.append_event(
                project_path=context.project_path,
                session_id=bound_session_id,
                type=EventType.QUARANTINE_LIFTED.value,
                source="security_review",
                payload={"promoted_event_id": event_id, "reason": "manual_promotion"},
                caused_by=event_id,
                importance=5,
                _session=db,
            )
            audit_tool_call(
                context,
                tool_name="promote_event",
                tool_args={"event_id": event_id},
                session_id=bound_session_id,
                _session=db,
            )
            db.commit()
            result_data = event_to_read(event).model_dump(mode="json")
        logger.warning(
            "security_event",
            extra={
                "event": "quarantine_lifted",
                "promoted_event_id": event_id,
            },
        )
        return {"ok": True, "data": result_data}


def register_tools(mcp, context: BrainContext) -> None:
    _register_save_event(mcp, context)
    _register_list_events(mcp, context)
    _register_review_quarantined(mcp, context)
    _register_promote_event(mcp, context)
