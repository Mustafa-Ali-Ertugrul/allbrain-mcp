from __future__ import annotations

from typing import Any

from allbrain.graph import WorkflowGraphBuilder
from allbrain.models.schemas import EventRead


class GraphSnapshotBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        graph = WorkflowGraphBuilder().build(events)
        return {
            "kind": "graph_snapshot",
            "event_cursor": events[-1].id if events else None,
            "graph": graph,
            "event_count": len(events),
        }
