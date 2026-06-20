from __future__ import annotations

from allbrain.memory.semantic_memory import MemoryItem, SemanticMemory


class MemoryRetriever:
    def __init__(self, items: list[MemoryItem]):
        self.items = items
        self.semantic = SemanticMemory()

    def retrieve_similar_workflows(self, query: str, *, top_k: int = 5) -> list[dict[str, object]]:
        return self._rank(query, kind="workflow", top_k=top_k)

    def retrieve_agent_experience(self, agent_id: str, *, top_k: int = 5) -> list[dict[str, object]]:
        matches = [item for item in self.items if item.tags.get("agent") == agent_id]
        return [self._result(item, 1.0) for item in matches[:top_k]]

    def retrieve_failure_patterns(self, query: str = "", *, top_k: int = 5) -> list[dict[str, object]]:
        return self._rank(query or "failure pattern", kind="failure_pattern", top_k=top_k)

    def _rank(self, query: str, *, kind: str, top_k: int) -> list[dict[str, object]]:
        query_embedding = self.semantic.embed(query)
        ranked = [
            self._result(item, self.semantic.similarity(query_embedding, item.embedding))
            for item in self.items
            if item.tags.get("kind") == kind
        ]
        ranked.sort(key=lambda item: (-float(item["score"]), str(item["id"])))
        return ranked[:top_k]

    def _result(self, item: MemoryItem, score: float) -> dict[str, object]:
        data = item.to_dict()
        data["score"] = score
        return data
