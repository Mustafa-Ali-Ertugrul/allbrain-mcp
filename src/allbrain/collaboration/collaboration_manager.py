from __future__ import annotations

from allbrain.collaboration.collaboration_context import CollaborationContext
from allbrain.collaboration.collaboration_state import CollaborationStateBuilder
from allbrain.collaboration.team import AgentTeam


class CollaborationManager:
    def start_payload(self, context: CollaborationContext, team: AgentTeam | None = None) -> dict[str, object]:
        payload = context.to_dict()
        if team is not None:
            payload["team"] = team.to_dict()
        return payload

    def complete_payload(self, collaboration_id: str, *, outcome: str) -> dict[str, str]:
        return {"collaboration_id": collaboration_id, "status": "completed", "outcome": outcome}

    def state_from_events(self, events):
        return CollaborationStateBuilder().build(events)
