from __future__ import annotations

from typing import Any

from allbrain.graph import WorkflowGraphBuilder
from allbrain.models.schemas import EventRead
from allbrain.orchestrator import TaskStateReducer


class SnapshotManager:
    def restore_workflow(
        self, *, snapshot_state: dict[str, Any] | None, remaining_events: list[EventRead]
    ) -> dict[str, Any]:
        base = dict(snapshot_state or {})
        delta = TaskStateReducer().build(remaining_events)
        workflow_state = dict(base.get("workflow_state") or base.get("task_view") or {})
        if remaining_events:
            workflow_state.update(delta)
        return {
            "snapshot_hit": snapshot_state is not None,
            "workflow_state": workflow_state,
            "replayed_event_count": len(remaining_events),
        }

    def restore_graph(
        self, *, snapshot_state: dict[str, Any] | None, remaining_events: list[EventRead]
    ) -> dict[str, Any]:
        if snapshot_state and "graph" in snapshot_state and not remaining_events:
            return {"snapshot_hit": True, "graph": snapshot_state["graph"], "replayed_event_count": 0}
        graph = WorkflowGraphBuilder().build(remaining_events)
        return {
            "snapshot_hit": snapshot_state is not None,
            "graph": graph,
            "replayed_event_count": len(remaining_events),
        }
