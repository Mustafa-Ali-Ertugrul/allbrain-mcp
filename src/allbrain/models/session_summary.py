from __future__ import annotations

from datetime import datetime
from typing import Any

from allbrain.events import EventType
from allbrain.models.entities import Session, utc_now

_LIFECYCLE_TYPES = {
    EventType.TOOL_CALL.value,
    EventType.TOOL_CALL_OUTCOME.value,
    EventType.SESSION_STARTED.value,
    EventType.SESSION_SUMMARY.value,
}


def build_session_summary(
    session: Session,
    events: list[Any],
    *,
    status: str,
    reason: str,
    git: dict[str, Any] | None = None,
    ended_at: datetime | None = None,
) -> dict[str, Any]:
    semantic = [event for event in events if event.type not in _LIFECYCLE_TYPES]
    goals: list[str] = []
    task_ids: list[str] = []
    tools: list[str] = []
    errors: list[str] = []
    files: list[str] = []
    for event in events:
        payload = event.payload
        if event.type == EventType.TOOL_CALL.value:
            tool = payload.get("tool_name")
            if isinstance(tool, str):
                tools.append(tool)
        if event.type == EventType.TOOL_CALL_OUTCOME.value and not payload.get("ok", True):
            error = payload.get("error") or payload.get("error_type")
            if isinstance(error, str) and error:
                errors.append(error)
        goal = payload.get("goal") or payload.get("description") or payload.get("objective")
        if isinstance(goal, dict):
            goal = goal.get("goal") or goal.get("description") or str(goal)
        if isinstance(goal, str) and goal:
            goals.append(goal)
        task_id = payload.get("task_id")
        if isinstance(task_id, str) and task_id:
            task_ids.append(task_id)
        if event.file_path:
            files.append(event.file_path)
    return {
        "session_id": session.id,
        "agent": session.agent_name,
        "client_name": session.client_name,
        "client_version": session.client_version,
        "server_instance_id": session.server_instance_id,
        "status": status,
        "close_reason": reason,
        "started_at": session.started_at.isoformat(),
        "ended_at": (ended_at or session.ended_at or utc_now()).isoformat(),
        "semantic_event_count": len(semantic),
        "event_count": len(events),
        "goals": list(dict.fromkeys(goals)),
        "task_ids": list(dict.fromkeys(task_ids)),
        "tools": list(dict.fromkeys(tools)),
        "errors": list(dict.fromkeys(errors)),
        "files": sorted(set(files)),
        "file_changes": _count_file_changes(events),
        "git": git or {},
    }


def _count_file_changes(events: list[Any]) -> dict[str, int]:
    counts = {"added": 0, "modified": 0, "deleted": 0}
    for event in events:
        if event.type == EventType.FILE_MODIFIED.value:
            kind = event.payload.get("change_kind")
            if kind in counts:
                counts[kind] += 1
    return counts
