from __future__ import annotations

from typing import Any

from allbrain.domains.governance.governance.autonomy import AutonomyBoundaryController
from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class GovernanceStateBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        state: dict[str, Any] = {
            "reviews": {},
            "decisions": {},
            "constraints": {},
            "post_checks": {},
            "current_autonomy_level": 0,
        }
        successful_post_checks = 0
        for event in canonical_event_sort(events):
            payload = event.payload
            review_id = payload.get("review_id")
            decision_id = payload.get("decision_id")
            if event.type == EventType.GOVERNANCE_REVIEW_INITIATED.value and isinstance(review_id, str):
                state["reviews"][review_id] = {
                    "review_id": review_id,
                    "status": "initiated",
                    "events": [event.id],
                    **payload,
                }
            elif event.type == EventType.GOVERNANCE_ALIGNMENT_EVALUATED.value and isinstance(review_id, str):
                review = state["reviews"].setdefault(
                    review_id, {"review_id": review_id, "status": "initiated", "events": []}
                )
                review["alignment_report"] = dict(payload)
                review["events"].append(event.id)
            elif event.type == EventType.GOVERNANCE_TRAJECTORY_SIMULATED.value and isinstance(review_id, str):
                review = state["reviews"].setdefault(
                    review_id, {"review_id": review_id, "status": "initiated", "events": []}
                )
                review["trajectory"] = dict(payload)
                review["events"].append(event.id)
            elif event.type == EventType.GOVERNANCE_AUTONOMY_ASSESSED.value and isinstance(review_id, str):
                review = state["reviews"].setdefault(
                    review_id, {"review_id": review_id, "status": "initiated", "events": []}
                )
                review["autonomy"] = dict(payload)
                review["events"].append(event.id)
            elif event.type == EventType.GOVERNANCE_DECISION_SYNTHESIZED.value and isinstance(decision_id, str):
                state["decisions"][decision_id] = {"event_id": event.id, **payload}
                if isinstance(review_id, str):
                    review = state["reviews"].setdefault(
                        review_id, {"review_id": review_id, "status": "initiated", "events": []}
                    )
                    review["status"] = str(payload.get("decision", "decided"))
                    review["decision_id"] = decision_id
                    review["events"].append(event.id)
                state["current_autonomy_level"] = max(
                    state["current_autonomy_level"], int(payload.get("autonomy_level_allowed", 0) or 0)
                )
            elif event.type == EventType.GOVERNANCE_CONSTRAINTS_APPLIED.value and isinstance(review_id, str):
                state["constraints"][review_id] = {"event_id": event.id, **payload}
            elif event.type == EventType.GOVERNANCE_POST_CHECK_COMPLETED.value and isinstance(review_id, str):
                state["post_checks"][review_id] = {"event_id": event.id, **payload}
                if payload.get("status") == "success" or payload.get("alignment_preserved") is True:
                    successful_post_checks += 1
        state["current_autonomy_level"] = AutonomyBoundaryController().next_allowed_level_from_events(
            successful_post_checks, state["current_autonomy_level"]
        )
        return state


def is_governance_event(event: EventRead) -> bool:
    return event.type.startswith("governance_")
