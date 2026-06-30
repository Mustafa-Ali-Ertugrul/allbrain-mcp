from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.models.schemas import EventRead


class CounterfactualProjection:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        generated: list[dict[str, Any]] = []
        evaluated: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []
        unknown_actions: list[str] = []
        for event in canonical_event_sort(events):
            if event.type == EventType.COUNTERFACTUAL_GENERATED.value:
                generated.append(event.payload)
                if event.payload.get("reason") == "unknown_action":
                    action = event.payload.get("action")
                    if isinstance(action, str):
                        unknown_actions.append(action)
            elif event.type == EventType.COUNTERFACTUAL_EVALUATED.value:
                evaluated.append(event.payload)
            elif event.type == EventType.COUNTERFACTUAL_RECOMMENDATION.value:
                recommendations.append(event.payload)
        return {
            "analyses": evaluated,
            "generated": generated,
            "recommendations": recommendations,
            "unknown_actions": unknown_actions,
            "count": len(evaluated),
            "unknown_action_count": len(unknown_actions),
            "recommendation_count": len(recommendations),
        }
