from __future__ import annotations

from typing import Any


class TaskGraphBuilder:
    def build(self, task_state: dict[str, Any]) -> dict[str, Any]:
        tasks = task_state.get("tasks", {})
        nodes = [
            {
                "task_id": task_id,
                "goal": task.get("goal"),
                "status": task.get("status"),
                "owner": task.get("owner"),
                "priority": task.get("priority"),
            }
            for task_id, task in sorted(tasks.items())
        ]
        edges = [
            {
                "from": dependency["depends_on"],
                "to": dependency["task_id"],
                "edge_type": "depends_on",
            }
            for dependency in task_state.get("dependencies", [])
        ]
        edges.extend(
            {
                "from": handoff.get("from_agent"),
                "to": handoff.get("to_agent"),
                "task_id": handoff.get("task_id"),
                "edge_type": "handoff",
            }
            for handoff in task_state.get("handoffs", [])
            if handoff.get("from_agent") and handoff.get("to_agent")
        )
        return {"nodes": nodes, "edges": edges}
