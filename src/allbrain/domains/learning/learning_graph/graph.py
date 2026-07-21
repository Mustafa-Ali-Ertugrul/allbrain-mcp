from __future__ import annotations

from typing import Any

from allbrain.domains.learning.learning_graph.model import LearningNode


class LearningGraph:
    """DAG of learning pipeline nodes.

    Topology is FROZEN after creation. No add/remove nodes at runtime.
    Only node performance and numeric params are mutable via rewriter.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, LearningNode] = {}

    def add_node(self, node: LearningNode) -> None:
        if node.node_id in self._nodes:
            raise ValueError(f"Node {node.node_id} already exists")
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> LearningNode | None:
        return self._nodes.get(node_id)

    def update_performance(self, node_id: str, performance: float) -> LearningNode | None:
        node = self._nodes.get(node_id)
        if node is None:
            return None
        node.performance = max(0.0, min(1.0, performance))
        node.version += 1
        return node

    def worst_node(self) -> LearningNode | None:
        if not self._nodes:
            return None
        return min(self._nodes.values(), key=lambda n: n.performance)

    def all_nodes(self) -> dict[str, LearningNode]:
        return dict(self._nodes)

    def validate_topology(self) -> bool:
        for _nid, node in self._nodes.items():
            for dep in node.dependencies:
                if dep not in self._nodes:
                    return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {nid: n.to_dict() for nid, n in self._nodes.items()}
