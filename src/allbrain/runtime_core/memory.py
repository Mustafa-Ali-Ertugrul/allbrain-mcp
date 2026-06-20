from __future__ import annotations

from typing import Any

from allbrain.memory import MemoryBuilder, MemoryRetriever, WorkflowMemoryStore
from allbrain.models.schemas import EventRead


class GlobalExperienceMemoryBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        items = MemoryBuilder().build(events)
        categories = {
            "workflow": [],
            "economic": [],
            "execution": [],
            "arbitration": [],
            "governance": [],
        }
        for item in items:
            kind = str(item.tags.get("kind", ""))
            if kind in {"workflow", "failure_pattern", "fallback_pattern"}:
                categories["workflow"].append(item.to_dict())
            elif kind in {"governance_decision", "alignment_report"}:
                categories["governance"].append(item.to_dict())
        for event in events:
            if event.type in {"economic_evaluation_completed"}:
                categories["economic"].append({"id": f"economic:{event.id}", "payload": event.payload})
            elif event.type in {"execution_plan_created", "runtime_feedback_recorded"}:
                categories["execution"].append({"id": f"execution:{event.id}", "payload": event.payload})
            elif event.type == "arbitration_completed":
                categories["arbitration"].append({"id": f"arbitration:{event.id}", "payload": event.payload})
        store = WorkflowMemoryStore(items)
        return {"categories": categories, "store": store.to_dict(), "retriever": MemoryRetriever(items)}
