from __future__ import annotations

from typing import Any


class GraphQueryEngine:
    def __init__(self, graph: dict[str, Any]):
        self.graph = graph

    def find_paths(self, *, agent: str | None = None, failed: bool | None = None) -> list[list[str]]:
        nodes = self.graph.get("nodes", {})
        edges = self.graph.get("edges", [])
        adjacency: dict[str, list[str]] = {}
        reverse: dict[str, list[str]] = {}
        for edge in edges:
            adjacency.setdefault(edge["from"], []).append(edge["to"])
            reverse.setdefault(edge["to"], []).append(edge["from"])
        starts = [
            node_id
            for node_id, node in nodes.items()
            if (agent is None or node.get("agent_id") == agent)
            and (failed is None or bool(node.get("failed")) == failed)
        ]
        paths = [[start, nxt] for start in starts for nxt in sorted(adjacency.get(start, []))]
        paths.extend([[prev, start] for start in starts for prev in sorted(reverse.get(start, []))])
        return paths or [[start] for start in starts]

    def get_cost_by_workflow(self, workflow_id: str) -> float:
        nodes = self.graph.get("nodes", {})
        task_prefix = f"task:{workflow_id}"
        return sum(
            float(node.get("cost_usd", 0.0) or 0.0)
            for node in nodes.values()
            if node.get("task_id") == workflow_id or str(node.get("id", "")).startswith(task_prefix)
        )

    def most_expensive_agent(self) -> dict[str, Any] | None:
        costs: dict[str, float] = {}
        for node in self.graph.get("nodes", {}).values():
            agent_id = node.get("agent_id")
            if isinstance(agent_id, str):
                costs[agent_id] = costs.get(agent_id, 0.0) + float(node.get("cost_usd", 0.0) or 0.0)
        if not costs:
            return None
        agent_id = max(costs, key=costs.get)
        return {"agent_id": agent_id, "cost_usd": costs[agent_id]}
