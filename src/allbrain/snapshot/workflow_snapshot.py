from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.orchestrator import TaskStateReducer


class WorkflowSnapshotBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        task_state = TaskStateReducer().build(events)
        return {
            "kind": "workflow_snapshot",
            "event_cursor": events[-1].id if events else None,
            "workflow_state": task_state,
            "event_count": len(events),
        }
