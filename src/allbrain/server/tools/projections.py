"""Response-size projections for MCP tool outputs."""

from __future__ import annotations

from typing import Any

_SLIM_LIST_CAP = 20
_SLIM_FILES_CAP = 30
_SLIM_TASKS_CAP = 25
_FULL_FILES_CAP = 200
_FULL_TOOL_USAGE_CAP = 50


def _cap_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[:limit]


def cap_full_resume_view(data: dict[str, Any]) -> dict[str, Any]:
    """Soft-cap unbounded lists in full resume payloads (token/DoS guard)."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    out["detail"] = "full"
    if isinstance(out.get("working_files"), list):
        out["working_files"] = out["working_files"][:_FULL_FILES_CAP]
    if isinstance(out.get("tool_usage"), list):
        out["tool_usage"] = out["tool_usage"][:_FULL_TOOL_USAGE_CAP]
    return out


def slim_resume_view(data: dict[str, Any]) -> dict[str, Any]:
    """Project multi-agent resume payload to a compact agent-facing view."""
    working = data.get("working_files") or []
    if isinstance(working, list) and len(working) > _SLIM_FILES_CAP:
        working = working[:_SLIM_FILES_CAP]
    git = data.get("git")
    git_slim: dict[str, Any] | None = None
    if isinstance(git, dict):
        git_slim = {key: git[key] for key in ("branch", "head", "is_repo") if key in git}
    decision = data.get("decision_view") if isinstance(data.get("decision_view"), dict) else {}
    conflict = data.get("conflict_view") if isinstance(data.get("conflict_view"), dict) else {}
    return {
        "detail": "slim",
        "goal": data.get("goal"),
        "open_tasks": _cap_list(data.get("open_tasks"), _SLIM_LIST_CAP),
        "completed": _cap_list(data.get("completed") or data.get("completed_tasks"), _SLIM_LIST_CAP),
        "blocked": _cap_list(data.get("blocked"), _SLIM_LIST_CAP),
        "failures": _cap_list(data.get("failures"), _SLIM_LIST_CAP),
        "working_files": working if isinstance(working, list) else [],
        "next_step": data.get("next_step") or decision.get("next_step"),
        "conflict_count": int(conflict.get("count") or 0),
        "git": git_slim,
    }


def slim_orchestrate_view(data: dict[str, Any]) -> dict[str, Any]:
    """Project orchestration payload to task/agent summary without nested megablobs."""
    task_view = data.get("task_view") if isinstance(data.get("task_view"), dict) else {}
    tasks = task_view.get("tasks") if isinstance(task_view.get("tasks"), dict) else {}
    open_ids = task_view.get("open_task_ids") if isinstance(task_view.get("open_task_ids"), list) else []
    completed_ids = task_view.get("completed_task_ids") if isinstance(task_view.get("completed_task_ids"), list) else []
    deleted_ids = task_view.get("deleted_task_ids") if isinstance(task_view.get("deleted_task_ids"), list) else []
    agent_queue = task_view.get("agent_queue") if isinstance(task_view.get("agent_queue"), dict) else {}
    top_tasks: list[dict[str, Any]] = []
    for task_id in list(open_ids)[:_SLIM_TASKS_CAP]:
        task = tasks.get(task_id) if isinstance(tasks, dict) else None
        if not isinstance(task, dict):
            top_tasks.append({"task_id": task_id})
            continue
        top_tasks.append(
            {
                "task_id": task.get("task_id", task_id),
                "goal": task.get("goal"),
                "status": task.get("status"),
                "owner": task.get("owner"),
                "priority": task.get("priority"),
            }
        )
    decision = data.get("decision_view") if isinstance(data.get("decision_view"), dict) else {}
    global_view = data.get("global_view") if isinstance(data.get("global_view"), dict) else {}
    return {
        "detail": "slim",
        "open_task_count": len(open_ids),
        "completed_task_count": len(completed_ids),
        "deleted_task_count": len(deleted_ids),
        "open_tasks": top_tasks,
        "agent_queue": {agent: list(queue)[:_SLIM_LIST_CAP] for agent, queue in agent_queue.items()},
        "decision_view": {
            "next_step": decision.get("next_step"),
            "required_action": decision.get("required_action"),
            "confidence": decision.get("confidence"),
        },
        "goal": global_view.get("goal"),
        "next_step": global_view.get("next_step") or decision.get("next_step"),
        "orchestrator_snapshot_used": global_view.get("orchestrator_snapshot_used"),
    }
