"""Reusable MCP prompts for AllBrain workflows."""

from __future__ import annotations

import json
import logging
from typing import Any

from allbrain.security.redaction import sanitize_text
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import load_events_through_cursor, load_task_projection
from allbrain.storage.database import open_session

logger = logging.getLogger(__name__)


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str, sort_keys=True)


def register_prompts(mcp: Any, context: BrainContext) -> None:
    @mcp.prompt
    def resume_project(limit: int = 5000) -> list[dict[str, str]]:
        project = context.repository.get_project_by_path(context.project_path)
        if project is None:
            return [
                {
                    "role": "user",
                    "content": sanitize_text(
                        f"No project found at {context.project_path}. Initialize a project first."
                    ),
                },
            ]
        events = load_events_through_cursor(
            context.repository,
            project_path=context.project_path,
            batch_size=limit,
        )
        task_state, _ = load_task_projection(
            context,
            project_id=project.id,
            batch_size=limit,
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
        return [
            {
                "role": "user",
                "content": sanitize_text(
                    f"Resume work on project at {context.project_path}. Context summary:\n{summary}"
                ),
            },
            {
                "role": "assistant",
                "content": sanitize_text(
                    "I will review the project state and continue from "
                    "the last checkpoint. Let me check recent events "
                    "and task status."
                ),
            },
        ]

    @mcp.prompt
    def task_handoff(
        task_id: str,
        from_agent: str,
        reason: str | None = None,
    ) -> list[dict[str, str]]:
        project = context.repository.get_project_by_path(context.project_path)
        if project is None:
            return [
                {
                    "role": "user",
                    "content": sanitize_text(f"Cannot handoff task {task_id}: no project found."),
                },
            ]
        task_state, _ = load_task_projection(
            context,
            project_id=project.id,
            batch_size=5000,
        )
        tasks_dict = task_state.get("tasks", {})
        task = tasks_dict.get(task_id)
        task_info = _json_text(task) if task else f"Task {task_id} not found in projections"
        reason_text = sanitize_text(reason) if reason else "No reason provided"
        return [
            {
                "role": "user",
                "content": sanitize_text(
                    f"Handoff task {task_id} from agent {from_agent}. Reason: {reason_text}\nTask state:\n{task_info}"
                ),
            },
            {
                "role": "assistant",
                "content": sanitize_text(
                    f"Received handoff of task {task_id} from {from_agent}. "
                    "I will review the task state and continue execution."
                ),
            },
        ]

    @mcp.prompt
    def investigate_conflict(session_id: int) -> list[dict[str, str]]:
        project = context.repository.get_project_by_path(context.project_path)
        if project is None:
            return [
                {
                    "role": "user",
                    "content": sanitize_text(
                        f"Cannot investigate conflict for session {session_id}: no project found."
                    ),
                },
            ]
        with open_session(context.repository.engine) as db:
            session = context.repository.get_session(db, session_id)
            if session is None or session.project_id != project.id:
                return [
                    {
                        "role": "user",
                        "content": sanitize_text(f"Session {session_id} not found in this project."),
                    },
                ]
            agent_name = session.agent_name
        events = context.repository.list_events(
            project_path=context.project_path,
            session_id=session_id,
            limit=500,
        )
        conflict_events = [e for e in events if e.type in ("conflict_detected", "resolve_conflicts", "handoff_created")]
        summary = _json_text(
            {
                "session_id": session_id,
                "agent_name": agent_name,
                "total_events": len(events),
                "conflict_events": [{"id": e.id, "type": e.type, "payload": e.payload} for e in conflict_events],
            }
        )
        return [
            {
                "role": "user",
                "content": sanitize_text(
                    f"Investigate conflict in session {session_id} (agent: {agent_name}).\nContext:\n{summary}"
                ),
            },
            {
                "role": "assistant",
                "content": sanitize_text(
                    "I will analyze the conflict events and session history "
                    "to understand the root cause and suggest resolution."
                ),
            },
        ]
