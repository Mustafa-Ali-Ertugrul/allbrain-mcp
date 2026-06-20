from __future__ import annotations

from collections import defaultdict

from allbrain.intent.models import Intent


class IntentGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, list[dict]] = defaultdict(list)

    def add_intent(self, intent: Intent) -> None:
        self.nodes[intent.intent_id] = intent.model_dump(mode="json")

    def link(self, from_id: str, to_id: str, edge_type: str) -> None:
        edge = {"from": from_id, "to": to_id, "edge_type": edge_type}
        if edge not in self.edges[from_id]:
            self.edges[from_id].append(edge)

    def to_dict(self) -> dict:
        return {"nodes": self.nodes, "edges": dict(self.edges)}
