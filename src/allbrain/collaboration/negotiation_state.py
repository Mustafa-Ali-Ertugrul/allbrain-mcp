from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NegotiationState:
    negotiation_id: str
    participants: list[str]
    status: str = "active"
    proposals: list[dict[str, Any]] = field(default_factory=list)

    def add_proposal(self, proposal: dict[str, Any]) -> None:
        self.proposals.append(proposal)

    def accept(self, proposal_id: str) -> None:
        self.status = "accepted"
        for proposal in self.proposals:
            if proposal.get("proposal_id") == proposal_id:
                proposal["status"] = "accepted"

    def reject(self, proposal_id: str) -> None:
        for proposal in self.proposals:
            if proposal.get("proposal_id") == proposal_id:
                proposal["status"] = "rejected"

    def timeout(self) -> None:
        self.status = "timeout"
