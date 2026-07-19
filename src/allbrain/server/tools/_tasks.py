"""Task lookup, selection decisions, metrics merging, and observability helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from math import log
from typing import Any

from allbrain.models.schemas import UserInputError
from allbrain.server.context import BrainContext


def datetime_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def semantic_event_count(events) -> int:
    return sum(1 for event in events if event.type != "tool_call")


def get_task_or_raise(task_state: dict[str, Any], task_id: str) -> dict[str, Any]:
    tasks_dict = task_state.get("tasks") if isinstance(task_state, dict) else None
    task = tasks_dict.get(task_id) if isinstance(tasks_dict, dict) else task_state.get(task_id)
    if task is None:
        raise UserInputError(f"Task {task_id} not found")
    return task


def append_selection_decision(
    context: BrainContext,
    *,
    project_path: str,
    session_id: int,
    task_id: str,
    assignment: dict[str, Any],
    assignment_event_id: str,
    task_hint: str | None,
    caused_by: str | None = None,
    _session: Any | None = None,
):
    from allbrain.events import EventType

    selection_decision = assignment.get("selection_decision", {})
    return context.repository.append_event(
        project_path=project_path,
        session_id=session_id,
        type=EventType.SELECTION_DECISION.value,
        source="allbrain",
        payload={
            "task_id": task_id,
            "assignment_event_id": assignment_event_id,
            "agent_id": assignment["agent_id"],
            "total_score": assignment["score"],
            "breakdown": assignment["breakdown"],
            "reason": assignment["reason"],
            "fallback_mode": assignment.get("fallback_mode", False),
            "selection_decision": selection_decision,
        },
        agent_id=assignment["agent_id"],
        task_hint=task_hint,
        caused_by=caused_by or assignment_event_id,
        _session=_session,
    )


def observability_project_and_limit(context: BrainContext, kwargs: dict[str, Any]) -> tuple[str, int]:
    project_path = context.project_path
    limit = int(kwargs.get("limit", 5000) or 5000)
    if limit < 1 or limit > 50000:
        raise UserInputError("limit must be between 1 and 50000")
    return project_path, limit


def filter_observability_events(
    events,
    *,
    workflow_id: str | None = None,
    task_id: str | None = None,
):
    if workflow_id is None and task_id is None:
        return events
    return [
        event
        for event in events
        if (
            workflow_id is None
            or event.payload.get("workflow_id") == workflow_id
            or event.payload.get("root_task_id") == workflow_id
            or event.payload.get("task_id") == workflow_id
        )
        and (task_id is None or event.payload.get("task_id") == task_id)
    ]


def merge_agent_metrics(base: dict[str, dict[str, Any]], delta: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not base:
        return delta
    merged: dict[str, dict[str, Any]] = {agent_id: dict(metrics) for agent_id, metrics in base.items()}
    for agent_id, delta_metrics in delta.items():
        from allbrain.orchestrator.metrics import AgentPerformanceReducer

        metrics = merged.setdefault(
            agent_id,
            AgentPerformanceReducer()
            .reduce([])
            .get(
                agent_id,
                {
                    "agent_id": agent_id,
                    "success_count": 0,
                    "failure_count": 0,
                    "blocked_count": 0,
                    "assigned_count": 0,
                    "total_tasks": 0,
                    "success_rate": 0.0,
                    "failure_rate": 0.0,
                    "blocked_rate": 0.0,
                    "confidence": 0.0,
                },
            ),
        )
        for key in ["success_count", "failure_count", "blocked_count", "assigned_count"]:
            metrics[key] = int(metrics.get(key, 0)) + int(delta_metrics.get(key, 0))
        total_tasks = metrics["success_count"] + metrics["failure_count"] + metrics["blocked_count"]
        metrics["total_tasks"] = total_tasks
        denominator = max(1, total_tasks)
        metrics["success_rate"] = metrics["success_count"] / denominator
        metrics["failure_rate"] = metrics["failure_count"] / denominator
        metrics["blocked_rate"] = metrics["blocked_count"] / denominator
        metrics["confidence"] = min(1.0, log(total_tasks + 1) / log(50))
    return dict(sorted(merged.items()))
