from __future__ import annotations

from typing import Any

from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class LearningStateBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        state: dict[str, Any] = {"cycles": {}, "patterns": {}, "recommendations": {}, "policy_updates": {}}
        for event in canonical_event_sort(events):
            payload = event.payload
            cycle_id = payload.get("cycle_id")
            if event.type in {
                EventType.LEARNING_CYCLE_STARTED.value,
                EventType.LEARNING_CYCLE_COMPLETED.value,
            } and isinstance(cycle_id, str):
                cycle = state["cycles"].setdefault(cycle_id, {"cycle_id": cycle_id, "status": "active", "events": []})
                cycle["status"] = "completed" if event.type == EventType.LEARNING_CYCLE_COMPLETED.value else "active"
                cycle["events"].append(event.id)
            pattern_id = payload.get("pattern_id")
            if event.type == EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value and isinstance(pattern_id, str):
                state["patterns"][pattern_id] = {"event_id": event.id, **payload}
            recommendation_id = payload.get("recommendation_id")
            if event.type in {
                EventType.RECOMMENDATION_GENERATED.value,
                EventType.RECOMMENDATION_APPLIED.value,
                EventType.RECOMMENDATION_REJECTED.value,
            } and isinstance(recommendation_id, str):
                recommendation = state["recommendations"].setdefault(
                    recommendation_id, {"recommendation_id": recommendation_id, "status": "generated"}
                )
                recommendation.update(payload)
                if event.type == EventType.RECOMMENDATION_APPLIED.value:
                    recommendation["status"] = "applied"
                elif event.type == EventType.RECOMMENDATION_REJECTED.value:
                    recommendation["status"] = "rejected"
            policy_update_id = payload.get("policy_update_id")
            if event.type in {
                EventType.POLICY_UPDATE_PROPOSED.value,
                EventType.POLICY_UPDATE_APPROVED.value,
                EventType.POLICY_UPDATE_REJECTED.value,
            } and isinstance(policy_update_id, str):
                update = state["policy_updates"].setdefault(
                    policy_update_id, {"policy_update_id": policy_update_id, "status": "proposed"}
                )
                update.update(payload)
                if event.type == EventType.POLICY_UPDATE_APPROVED.value:
                    update["status"] = "approved"
                elif event.type == EventType.POLICY_UPDATE_REJECTED.value:
                    update["status"] = "rejected"
        return state
