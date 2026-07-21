from __future__ import annotations

from typing import Any

from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class MetaReasoningProjection:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        started: list[dict[str, Any]] = []
        completed: list[dict[str, Any]] = []
        explanations: list[dict[str, Any]] = []
        analysis_ids: list[str] = []
        seen_ids: set[str] = set()
        for event in canonical_event_sort(events):
            if event.type == EventType.META_REASONING_STARTED.value:
                started.append(event.payload)
                aid = event.payload.get("foresight_analysis_id")
                if isinstance(aid, str) and aid not in seen_ids:
                    analysis_ids.append(aid)
                    seen_ids.add(aid)
            elif event.type == EventType.META_REASONING_COMPLETED.value:
                completed.append(event.payload)
            elif event.type == EventType.DECISION_EXPLAINED.value:
                explanations.append(event.payload)
        return {
            "started": started,
            "completed": completed,
            "explanations": explanations,
            "analysis_ids": analysis_ids,
            "count": len(explanations),
        }
