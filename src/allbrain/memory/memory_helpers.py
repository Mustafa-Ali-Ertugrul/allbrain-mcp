from __future__ import annotations

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


def _agent(event):
    value = (
        event.payload.get("agent_id")
        or event.payload.get("from_agent")
        or event.payload.get("to_agent")
        or event.agent_id
    )
    return value if isinstance(value, str) and value else None


def _task_summary(task_id: str, events: list[EventRead]) -> str:
    goal = next((event.payload.get("goal") for event in events if event.payload.get("goal")), task_id)
    status = _status(events)
    agents = ", ".join(dict.fromkeys(agent for event in events if (agent := _agent(event))))
    failure = _failure_reason(events)
    return f"task {task_id}: {goal}; status={status}; agents={agents or 'unknown'}; failure={failure or 'none'}"


def _status(events: list[EventRead]) -> str:
    if any(event.type == EventType.TASK_COMPLETED.value for event in events):
        return "success"
    if any(event.type in {EventType.TASK_FAILED.value, EventType.AGENT_EXECUTION_FAILED.value} for event in events):
        return "failed"
    if any(event.type == EventType.TASK_BLOCKED.value for event in events):
        return "blocked"
    return "active"


def _importance(events: list[EventRead]) -> float:
    if _status(events) == "failed":
        return 0.8
    if _status(events) == "success":
        return 0.7
    return 0.4


def _last_agent(events: list[EventRead]) -> str | None:
    for event in reversed(events):
        agent = _agent(event)
        if agent:
            return agent
    return None


def _failure_reason(events: list[EventRead]) -> str | None:
    for event in reversed(events):
        if event.type in {EventType.TASK_FAILED.value, EventType.AGENT_EXECUTION_FAILED.value}:
            reason = event.payload.get("reason") or event.payload.get("error") or event.payload.get("error_type")
            if isinstance(reason, str) and reason:
                return reason
    return None


def _failed_agent(events: list[EventRead]) -> str | None:
    for event in reversed(events):
        if event.type in {EventType.TASK_FAILED.value, EventType.AGENT_EXECUTION_FAILED.value}:
            agent = _agent(event)
            if agent:
                return agent
    return None


def _failure_pattern(task_id: str, events: list[EventRead]) -> str | None:
    reason = _failure_reason(events)
    agent = _failed_agent(events)
    if not reason:
        return None
    return f"failure pattern task={task_id} agent={agent or 'unknown'} reason={reason}"


def _fallback_pattern(task_id: str, events: list[EventRead]) -> str | None:
    assignments = [_agent(event) for event in events if event.type == EventType.TASK_ASSIGNED.value and _agent(event)]
    if len(assignments) < 2:
        return None
    return f"fallback pattern task={task_id}: {assignments[0]} -> {assignments[-1]} status={_status(events)}"
