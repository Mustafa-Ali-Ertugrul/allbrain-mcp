from __future__ import annotations

from allbrain.memory.memory_retriever import MemoryRetriever
from allbrain.memory.semantic_memory import MemoryItem


class WorkflowMemoryStore:
    def __init__(self, items: list[MemoryItem] | None = None):
        self.items = items or []

    def add_many(self, items: list[MemoryItem]) -> None:
        existing = {item.id for item in self.items}
        self.items.extend(item for item in items if item.id not in existing)

    def successful_workflows(self) -> list[MemoryItem]:
        return [item for item in self.items if item.tags.get("kind") == "workflow" and item.tags.get("status") == "success"]

    def failed_workflows(self) -> list[MemoryItem]:
        return [item for item in self.items if item.tags.get("kind") == "workflow" and item.tags.get("status") == "failed"]

    def patterns(self) -> list[MemoryItem]:
        return [item for item in self.items if item.tags.get("kind") in {"failure_pattern", "fallback_pattern"}]

    def retriever(self) -> MemoryRetriever:
        return MemoryRetriever(self.items)

    def to_dict(self) -> dict[str, object]:
        return {
            "items": [item.to_dict() for item in self.items],
            "successful_workflows": len(self.successful_workflows()),
            "failed_workflows": len(self.failed_workflows()),
            "patterns": len(self.patterns()),
        }
