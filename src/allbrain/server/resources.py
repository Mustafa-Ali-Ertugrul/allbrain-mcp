"""Read-only MCP resources for AllBrain project state."""

from __future__ import annotations

import json
import logging
from typing import Any

from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import load_task_projection
from allbrain.storage.database import open_session

logger = logging.getLogger(__name__)

_ERROR_RESPONSE = {"ok": False, "error": ""}


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str, sort_keys=True)


def _project_resume(context: BrainContext) -> dict[str, Any]:
    project = context.repository.get_project_by_path(context.project_path)
    if project is None:
        return {**_ERROR_RESPONSE, "error": "Project not found"}
    events = context.repository.list_events(project_path=context.project_path, limit=5000)
    return {
        "ok": True,
        "project_id": project.id,
        "project_path": context.project_path,
        "event_count": len(events),
        "session_count": len({e.session_id for e in events}),
        "agent_count": len({e.agent_id for e in events if e.agent_id}),
    }


def _tasks_graph(context: BrainContext) -> dict[str, Any]:
    project = context.repository.get_project_by_path(context.project_path)
    if project is None:
        return {**_ERROR_RESPONSE, "error": "Project not found"}
    task_state, metrics = load_task_projection(
        context,
        project_id=project.id,
        batch_size=5000,
    )
    return {
        "ok": True,
        "task_view": task_state,
        "agent_state": metrics,
    }


def _git_fingerprint(context: BrainContext) -> dict[str, Any]:
    baseline = context.git_baseline
    if baseline is None:
        return {
            "ok": True,
            "fingerprint": None,
            "message": "No git fingerprint available",
        }
    return {
        "ok": True,
        "fingerprint": baseline,
    }


def _session_summary(context: BrainContext, session_id: int) -> dict[str, Any]:
    project = context.repository.get_project_by_path(context.project_path)
    if project is None:
        return {**_ERROR_RESPONSE, "error": "Project not found"}
    with open_session(context.repository.engine) as db:
        session = context.repository.get_session(db, session_id)
    if session is None or session.project_id != project.id:
        return {**_ERROR_RESPONSE, "error": "Session not found"}
    events = context.repository.list_events(
        project_path=context.project_path,
        session_id=session_id,
        limit=5000,
    )
    return {
        "ok": True,
        "session_id": session_id,
        "agent_name": session.agent_name,
        "status": session.status,
        "event_count": len(events),
        "event_types": sorted({e.type for e in events}),
    }


def _event_by_id(context: BrainContext, event_id: str) -> dict[str, Any]:
    event = context.repository.get_event(event_id)
    if event is None:
        return {**_ERROR_RESPONSE, "error": "Event not found"}
    return {
        "ok": True,
        "id": event.id,
        "project_id": event.project_id,
        "session_id": event.session_id,
        "agent_id": event.agent_id,
        "type": event.type,
        "source": event.source,
        "payload": event.payload,
        "created_at": event.created_at,
    }


def register_resources(mcp: Any, context: BrainContext) -> None:
    @mcp.resource("project://resume")
    def project_resume() -> str:
        return _json(_project_resume(context))

    @mcp.resource("tasks://graph")
    def tasks_graph() -> str:
        return _json(_tasks_graph(context))

    @mcp.resource("git://fingerprint")
    def git_fingerprint() -> str:
        return _json(_git_fingerprint(context))

    @mcp.resource("session://{session_id}/summary")
    def session_summary(session_id: int) -> str:
        return _json(_session_summary(context, session_id))

    @mcp.resource("event://{event_id}")
    def event_by_id(event_id: str) -> str:
        return _json(_event_by_id(context, event_id))
