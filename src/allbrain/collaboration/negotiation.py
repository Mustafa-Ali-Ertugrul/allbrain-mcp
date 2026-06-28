from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from uuid6 import uuid7

from allbrain.collaboration.negotiation_state import NegotiationState
from allbrain.collaboration.proposal import Proposal, ProposalFactory


@dataclass
class NegotiationEngine:
    proposal_factory: ProposalFactory = ProposalFactory()

    def start(self, participants: list[str]) -> NegotiationState:
        return NegotiationState(negotiation_id=str(uuid7()), participants=list(participants))

    def propose(self, state: NegotiationState, *, agent_id: str, content: str) -> Proposal:
        proposal = self.proposal_factory.create(negotiation_id=state.negotiation_id, agent_id=agent_id, content=content)
        state.add_proposal(proposal.to_event_payload())
        return proposal

    def counter(self, state: NegotiationState, *, agent_id: str, content: str) -> Proposal:
        return self.propose(state, agent_id=agent_id, content=content)

    def event_payload(self, state: NegotiationState) -> dict[str, Any]:
        return {"negotiation_id": state.negotiation_id, "participants": state.participants, "status": state.status}
