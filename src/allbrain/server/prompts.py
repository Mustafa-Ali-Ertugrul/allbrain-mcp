"""Reusable MCP prompts for AllBrain workflows."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastmcp.prompts import Message, PromptResult

from allbrain.security.redaction import sanitize_text
from allbrain.server.context import BrainContext
from allbrain.server.tools._events import load_events_through_cursor, load_task_projection
from allbrain.storage.database import open_session

logger = logging.getLogger(__name__)


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str, sort_keys=True)


def _as_int(value: Any, default: int) -> int:
    """Coerce prompt arguments to int, tolerating MCP placeholder strings.

    Some MCP clients (e.g. OpenCode) prefetch prompts with literal
    template placeholders such as ``"$1"`` before real arguments exist.
    Non-numeric values therefore fall back to *default* instead of raising.
    """
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_conflict_summary(session_id: int, agent_name: str, events: list[Any]) -> str:
    conflict_types = ("conflict_detected", "resolve_conflicts", "handoff_created")
    conflict_events = [e for e in events if e.type in conflict_types]
    return _json_text(
        {
            "session_id": session_id,
            "agent_name": agent_name,
            "total_events": len(events),
            "conflict_events": [{"id": e.id, "type": e.type, "payload": e.payload} for e in conflict_events],
        }
    )


def register_prompts(mcp: Any, context: BrainContext) -> None:
    @mcp.prompt
    def resume_project(limit: str = "5000") -> PromptResult:
        event_limit = _as_int(limit, 5000)
        project = context.repository.get_project_by_path(context.project_path)
        if project is None:
            return PromptResult(
                [
                    Message(sanitize_text(f"No project found at {context.project_path}. Initialize a project first.")),
                ]
            )
        events = load_events_through_cursor(
            context.repository,
            project_path=context.project_path,
            batch_size=event_limit,
        )
        task_state, _ = load_task_projection(
            context,
            project_id=project.id,
            batch_size=event_limit,
        )
        recent_types = sorted({e.type for e in events[-20:]}) if events else []
        summary = _json_text(
            {
                "project_path": context.project_path,
                "total_events": len(events),
                "recent_event_types": recent_types,
                "tasks": task_state.get("tasks", {}),
            }
        )
        return PromptResult(
            [
                Message(
                    sanitize_text(f"Resume work on project at {context.project_path}. Context summary:\n{summary}")
                ),
                Message(
                    sanitize_text(
                        "I will review the project state and continue from "
                        "the last checkpoint. Let me check recent events "
                        "and task status."
                    ),
                    role="assistant",
                ),
            ]
        )

    @mcp.prompt
    def task_handoff(
        task_id: str,
        from_agent: str,
        reason: str | None = None,
    ) -> PromptResult:
        project = context.repository.get_project_by_path(context.project_path)
        if project is None:
            return PromptResult(
                [
                    Message(sanitize_text(f"Cannot handoff task {task_id}: no project found.")),
                ]
            )
        task_state, _ = load_task_projection(
            context,
            project_id=project.id,
            batch_size=5000,
        )
        tasks_dict = task_state.get("tasks", {})
        task = tasks_dict.get(task_id)
        task_info = _json_text(task) if task else f"Task {task_id} not found in projections"
        reason_text = sanitize_text(reason) if reason else "No reason provided"
        return PromptResult(
            [
                Message(
                    sanitize_text(
                        f"Handoff task {task_id} from agent {from_agent}. "
                        f"Reason: {reason_text}\nTask state:\n{task_info}"
                    )
                ),
                Message(
                    sanitize_text(
                        f"Received handoff of task {task_id} from {from_agent}. "
                        "I will review the task state and continue execution."
                    ),
                    role="assistant",
                ),
            ]
        )

    @mcp.prompt
    def investigate_conflict(session_id: str) -> PromptResult:
        sid = _as_int(session_id, 0)
        project = context.repository.get_project_by_path(context.project_path)
        if project is None or sid <= 0:
            return PromptResult(
                [
                    Message(
                        sanitize_text(
                            f"Cannot investigate conflict for session {session_id}: no project found."
                            if project is None
                            else f"Invalid session_id {session_id!r}; expected a positive integer."
                        )
                    ),
                ]
            )
        with open_session(context.repository.engine) as db:
            session = context.repository.get_session(db, sid)
            if session is None or session.project_id != project.id:
                return PromptResult(
                    [
                        Message(sanitize_text(f"Session {sid} not found in this project.")),
                    ]
                )
            agent_name = session.agent_name
        events = context.repository.list_events(
            project_path=context.project_path,
            session_id=sid,
            limit=500,
        )
        summary = _build_conflict_summary(sid, agent_name, events)
        return PromptResult(
            [
                Message(
                    sanitize_text(f"Investigate conflict in session {sid} (agent: {agent_name}).\nContext:\n{summary}")
                ),
                Message(
                    sanitize_text(
                        "I will analyze the conflict events and session history "
                        "to understand the root cause and suggest resolution."
                    ),
                    role="assistant",
                ),
            ]
        )
