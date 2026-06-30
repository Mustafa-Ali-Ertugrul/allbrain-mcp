from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.models.schemas import EventRead


class CollaborationStateBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        state: dict[str, Any] = {
            "collaborations": {},
            "delegations": {},
            "negotiations": {},
            "consensus": {},
            "supervisor_actions": [],
        }
        for event in canonical_event_sort(events):
            payload = event.payload
            collaboration_id = payload.get("collaboration_id")
            if event.type in {
                EventType.COLLABORATION_STARTED.value,
                EventType.COLLABORATION_COMPLETED.value,
                EventType.COLLABORATION_FAILED.value,
            } and isinstance(collaboration_id, str):
                collab = state["collaborations"].setdefault(
                    collaboration_id, {"collaboration_id": collaboration_id, "status": "active", "events": []}
                )
                collab.update(
                    {
                        key: payload.get(key)
                        for key in ["objective", "team_name", "task_id", "workflow_id"]
                        if payload.get(key) is not None
                    }
                )
                collab["status"] = _status(event.type)
                collab["events"].append(event.id)
            delegation_id = payload.get("delegation_id")
            if event.type in {
                EventType.DELEGATION_CREATED.value,
                EventType.DELEGATION_COMPLETED.value,
                EventType.DELEGATION_FAILED.value,
            } and isinstance(delegation_id, str):
                delegation = state["delegations"].setdefault(
                    delegation_id, {"delegation_id": delegation_id, "status": "created"}
                )
                delegation.update(
                    {
                        key: payload.get(key)
                        for key in ["from_agent", "to_agent", "task_id", "reason", "outcome"]
                        if payload.get(key) is not None
                    }
                )
                delegation["status"] = _status(event.type)
            negotiation_id = payload.get("negotiation_id")
            if event.type in {
                EventType.NEGOTIATION_STARTED.value,
                EventType.NEGOTIATION_COMPLETED.value,
                EventType.NEGOTIATION_TIMEOUT.value,
            } and isinstance(negotiation_id, str):
                negotiation = state["negotiations"].setdefault(
                    negotiation_id, {"negotiation_id": negotiation_id, "status": "active", "proposals": []}
                )
                negotiation["status"] = _status(event.type)
            if event.type in {
                EventType.PROPOSAL_CREATED.value,
                EventType.PROPOSAL_ACCEPTED.value,
                EventType.PROPOSAL_REJECTED.value,
            } and isinstance(negotiation_id, str):
                negotiation = state["negotiations"].setdefault(
                    negotiation_id, {"negotiation_id": negotiation_id, "status": "active", "proposals": []}
                )
                negotiation["proposals"].append(
                    {
                        "event_id": event.id,
                        "proposal_id": payload.get("proposal_id"),
                        "agent_id": payload.get("agent_id"),
                        "status": _status(event.type),
                        "content": payload.get("content"),
                    }
                )
            consensus_id = payload.get("consensus_id")
            if event.type in {
                EventType.VOTE_CAST.value,
                EventType.CONSENSUS_REACHED.value,
                EventType.CONSENSUS_FAILED.value,
            } and isinstance(consensus_id, str):
                consensus = state["consensus"].setdefault(
                    consensus_id, {"consensus_id": consensus_id, "votes": [], "status": "active"}
                )
                if event.type == EventType.VOTE_CAST.value:
                    consensus["votes"].append(
                        {
                            "agent_id": payload.get("agent_id"),
                            "vote": payload.get("vote"),
                            "weight": payload.get("weight", 1.0),
                        }
                    )
                else:
                    consensus["status"] = _status(event.type)
                    consensus["decision"] = payload.get("decision")
            if event.type == EventType.SUPERVISOR_INTERVENTION.value:
                state["supervisor_actions"].append({"event_id": event.id, **payload})
        return state


def _status(event_type: str) -> str:
    if event_type.endswith("completed") or event_type.endswith("accepted") or event_type.endswith("reached"):
        return "success"
    if event_type.endswith("failed") or event_type.endswith("rejected") or event_type.endswith("timeout"):
        return "failed"
    return "active"
