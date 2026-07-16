"""Domain module: compact agent context pack."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from allbrain.models.schemas import ContextPackInput, ToolResult
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import audit_tool_call, bind_session_id
from allbrain.server.tools.decorators import handle_tool_errors
from allbrain.server.tools.events import list_events_impl
from allbrain.server.tools.memory import retrieve_memory_impl
from allbrain.server.tools.sessions import build_session_report
from allbrain.server.tools.snapshots import resume_project_impl
from allbrain.server.tools.tasks import get_task_graph_impl


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _within_window(iso_ts: Any, *, cutoff: datetime) -> bool:
    parsed = _parse_iso(iso_ts)
    return parsed is not None and parsed >= cutoff


def _filter_events(events: Any, *, cutoff: datetime, limit: int) -> list[dict[str, Any]]:
    if not isinstance(events, list):
        return []
    filtered: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        created = event.get("created_at")
        if created is not None and not _within_window(created, cutoff=cutoff):
            continue
        filtered.append(
            {
                "id": event.get("id"),
                "type": event.get("type"),
                "created_at": event.get("created_at"),
                "source": event.get("source"),
                "task_hint": event.get("task_hint"),
                "file_path": event.get("file_path"),
            }
        )
        if len(filtered) >= limit:
            break
    return filtered


def _filter_session_details(details: Any, *, cutoff: datetime) -> list[dict[str, Any]]:
    if not isinstance(details, list):
        return []
    kept: list[dict[str, Any]] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        started = item.get("started_at")
        if started is not None and not _within_window(started, cutoff=cutoff):
            continue
        kept.append(
            {
                "session_id": item.get("session_id"),
                "agent": item.get("agent"),
                "status": item.get("status"),
                "started_at": item.get("started_at"),
                "event_count": item.get("event_count"),
                "close_reason": item.get("close_reason"),
            }
        )
    return kept


def _resolve_task_focus(context: BrainContext, task_id: str | None, limit: int) -> dict[str, Any] | None:
    if not task_id:
        return None
    graph = get_task_graph_impl(context, limit=limit)
    if not graph.ok or not isinstance(graph.data, dict):
        return None
    task_view = graph.data.get("task_view") if isinstance(graph.data.get("task_view"), dict) else {}
    tasks = task_view.get("tasks") if isinstance(task_view.get("tasks"), dict) else {}
    task = tasks.get(task_id)
    return task if isinstance(task, dict) else None


def _memory_query(*, explicit: str | None, task: dict[str, Any] | None, project: dict[str, Any] | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    if task and isinstance(task.get("goal"), str) and task["goal"].strip():
        return task["goal"].strip()
    if project:
        for key in ("goal", "next_step"):
            value = project.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "recent project work"


@handle_tool_errors
def get_context_pack_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = ContextPackInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    cutoff = datetime.now(UTC) - timedelta(hours=data.window_hours)

    resume = resume_project_impl(
        context,
        detail="slim",
        include_git=data.include_git,
        use_snapshot=True,
        limit=data.limit,
    )
    project = resume.data if resume.ok and isinstance(resume.data, dict) else None

    task = _resolve_task_focus(context, data.task_id, data.limit)
    query = _memory_query(explicit=data.query, task=task, project=project)

    memory = retrieve_memory_impl(context, query=query, limit=data.limit, top_k=data.top_k)
    events_result = list_events_impl(context, limit=min(data.event_limit, 100))
    sessions = build_session_report(
        context,
        limit=data.session_limit,
        include_empty=False,
        detail_limit=data.session_detail_limit,
    )

    pack = {
        "pack_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "window_hours": data.window_hours,
        "query": query,
        "task_id": data.task_id,
        "task": (
            {
                "task_id": task.get("task_id") or data.task_id,
                "goal": task.get("goal"),
                "status": task.get("status"),
                "owner": task.get("owner"),
                "priority": task.get("priority"),
            }
            if task
            else None
        ),
        "project": project,
        "sessions": {
            "session_count": sessions.get("session_count"),
            "agents": sessions.get("agents"),
            "statuses": sessions.get("statuses"),
            "details": _filter_session_details(sessions.get("details"), cutoff=cutoff),
        },
        "memory": memory.data if memory.ok else {"error": memory.error, "error_code": memory.error_code},
        "recent_events": _filter_events(
            events_result.data if events_result.ok else [],
            cutoff=cutoff,
            limit=data.event_limit,
        ),
        "sources": {
            "resume_ok": resume.ok,
            "memory_ok": memory.ok,
            "events_ok": events_result.ok,
        },
    }
    audit_tool_call(
        context,
        tool_name="get_context_pack",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data=pack)


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def get_context_pack(
        task_id: str | None = None,
        query: str | None = None,
        window_hours: int = 24,
        limit: int = 500,
        include_git: bool = True,
        top_k: int = 5,
        event_limit: int = 30,
        session_limit: int = 20,
        session_detail_limit: int = 8,
    ) -> dict[str, Any]:
        """Build a compact multi-source context pack for agent work.

        Combines slim project resume, recent sessions, memory hits, and recent
        events into one payload so agents avoid multi-tool megablobs.

        Args:
            task_id: Optional task to focus memory/query on.
            query: Optional memory query (defaults from task goal / project next_step).
            window_hours: Time window for sessions/events (default 24, max 720).
            limit: Event replay budget for resume/memory (default 500).
            include_git: Include slim git summary from resume (default True).
            top_k: Memory hits to return (default 5).
            event_limit: Max recent events in pack (default 30).
            session_limit: Max sessions to scan (default 20).
            session_detail_limit: Max session detail rows (default 8).
        """
        result = get_context_pack_impl(
            context,
            task_id=task_id,
            query=query,
            window_hours=window_hours,
            limit=limit,
            include_git=include_git,
            top_k=top_k,
            event_limit=event_limit,
            session_limit=session_limit,
            session_detail_limit=session_detail_limit,
        )
        return result.model_dump(mode="json")
