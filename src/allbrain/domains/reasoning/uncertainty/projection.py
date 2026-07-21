from __future__ import annotations

from typing import Any

from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class UncertaintyProjection:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        estimates: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []
        calibrations: list[dict[str, Any]] = []
        analysis_ids: list[str] = []
        seen_ids: set[str] = set()
        for event in canonical_event_sort(events):
            if event.type == EventType.UNCERTAINTY_ESTIMATED.value:
                estimates.append(event.payload)
                aid = event.payload.get("analysis_id")
                if isinstance(aid, str) and aid not in seen_ids:
                    analysis_ids.append(aid)
                    seen_ids.add(aid)
            elif event.type == EventType.KNOWLEDGE_GAP_DETECTED.value:
                gaps.append(event.payload)
            elif event.type == EventType.CONFIDENCE_CALIBRATED.value:
                calibrations.append(event.payload)
        return {
            "estimates": estimates,
            "gaps": gaps,
            "calibrations": calibrations,
            "analysis_ids": analysis_ids,
            "count": len(estimates),
        }
