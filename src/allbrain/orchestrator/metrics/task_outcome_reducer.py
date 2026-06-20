from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


TERMINAL_EVENTS = {
    EventType.TASK_COMPLETED.value: "completed",
    EventType.TASK_FAILED.value: "failed",
    EventType.TASK_BLOCKED.value: "blocked",
}


class TaskOutcomeReducer:
    def reduce(self, events: list[EventRead]) -> dict[str, dict[str, Any]]:
        outcomes: dict[str, dict[str, Any]] = {}
        for event in events:
            task_id = event.payload.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                continue
            outcome = outcomes.setdefault(task_id, self._empty(task_id))
            if event.type == EventType.TASK_STARTED.value and outcome["_started_at"] is None:
                outcome["_started_at"] = event.created_at
            elif event.type in TERMINAL_EVENTS:
                outcome["status"] = TERMINAL_EVENTS[event.type]
                outcome["_ended_at"] = event.created_at
                if event.type == EventType.TASK_FAILED.value:
                    outcome["retry_count"] += 1
            elif event.type == EventType.HANDOFF_CREATED.value:
                outcome["agent_changes"] += 1

        for outcome in outcomes.values():
            started_at = outcome.pop("_started_at")
            ended_at = outcome.pop("_ended_at")
            if started_at is not None and ended_at is not None:
                outcome["duration"] = max(0.0, (ended_at - started_at).total_seconds())
            else:
                outcome["duration"] = None
        return dict(sorted(outcomes.items()))

    def _empty(self, task_id: str) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "status": "active",
            "duration": None,
            "retry_count": 0,
            "agent_changes": 0,
            "_started_at": None,
            "_ended_at": None,
        }
