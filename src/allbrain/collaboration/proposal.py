from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from uuid6 import uuid7


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    negotiation_id: str
    agent_id: str
    content: str
    status: str = "created"

    def to_event_payload(self) -> dict[str, Any]:
        return self.__dict__.copy()


class ProposalFactory:
    def create(self, *, negotiation_id: str, agent_id: str, content: str) -> Proposal:
        return Proposal(proposal_id=str(uuid7()), negotiation_id=negotiation_id, agent_id=agent_id, content=content)
