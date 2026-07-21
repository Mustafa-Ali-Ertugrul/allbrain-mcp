from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.domains.memory.observability import ObservabilityBuilder


class ExecutionVisualizer:
    def timeline(self, events: list[EventRead]) -> dict[str, Any]:
        replay = ObservabilityBuilder().workflow_replay(events)
        return {
            "tasks": replay["tasks"],
            "task_count": replay["task_count"],
            "decision_points": [
                step for task in replay["tasks"].values() for step in task["timeline"] if "selection_decision" in step
            ],
        }
