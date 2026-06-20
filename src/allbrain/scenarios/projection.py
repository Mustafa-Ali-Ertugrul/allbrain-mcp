from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class ScenarioProjection:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        generated: list[dict[str, Any]] = []
        evaluated: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []
        analysis_ids: list[str] = []
        seen_ids: set[str] = set()
        for event in sorted(events, key=lambda item: (item.created_at, item.id)):
            if event.type == EventType.SCENARIO_GENERATED.value:
                generated.append(event.payload)
                aid = event.payload.get("analysis_id")
                if isinstance(aid, str) and aid not in seen_ids:
                    analysis_ids.append(aid)
                    seen_ids.add(aid)
            elif event.type == EventType.SCENARIO_EVALUATED.value:
                evaluated.append(event.payload)
            elif event.type == EventType.SCENARIO_RECOMMENDED.value:
                recommendations.append(event.payload)
                aid = event.payload.get("analysis_id")
                if isinstance(aid, str) and aid not in seen_ids:
                    analysis_ids.append(aid)
                    seen_ids.add(aid)
        return {
            "analyses": evaluated,
            "generated": generated,
            "recommendations": recommendations,
            "analysis_ids": analysis_ids,
            "count": len(evaluated),
            "recommendation_count": len(recommendations),
        }
