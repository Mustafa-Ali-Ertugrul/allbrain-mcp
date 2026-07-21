from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.models.schemas import EventRead


class InformationSeekingProjection:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        needs: list[dict[str, Any]] = []
        gains: list[dict[str, Any]] = []
        selections: list[dict[str, Any]] = []
        analysis_ids: list[str] = []
        seen_ids: set[str] = set()
        for event in canonical_event_sort(events):
            if event.type == EventType.INFORMATION_NEED_DETECTED.value:
                needs.append(event.payload)
            elif event.type == EventType.INFORMATION_GAIN_ESTIMATED.value:
                gains.append(event.payload)
            elif event.type == EventType.INFORMATION_ACTION_SELECTED.value:
                selections.append(event.payload)
                aid = event.payload.get("analysis_id")
                if isinstance(aid, str) and aid not in seen_ids:
                    analysis_ids.append(aid)
                    seen_ids.add(aid)
        return {
            "needs": needs,
            "gains": gains,
            "selections": selections,
            "analysis_ids": analysis_ids,
            "count": len(needs),
            "selection_count": len(selections),
        }
