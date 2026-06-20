from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.orchestrator import TaskStateReducer


class StateGraph:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        state = TaskStateReducer().build(events)
        return {
            "tasks": state["tasks"],
            "agent_queue": state["agent_queue"],
            "open_task_ids": state["open_task_ids"],
            "completed_task_ids": state["completed_task_ids"],
        }
