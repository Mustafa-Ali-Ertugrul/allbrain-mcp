from __future__ import annotations

from allbrain.collaboration.decision import Decision
from allbrain.collaboration.voting import Vote


class ConsensusEngine:
    def majority(self, votes: list[Vote]) -> Decision:
        yes = sum(1 for vote in votes if vote.accepted)
        no = len(votes) - yes
        return Decision(yes > no, "majority", yes, no, 0.5, "majority_accept" if yes > no else "majority_reject")

    def weighted(self, votes: list[Vote], *, threshold: float = 0.5) -> Decision:
        yes = sum(vote.weight for vote in votes if vote.accepted)
        total = sum(vote.weight for vote in votes) or 1.0
        no = total - yes
        approved = yes / total >= threshold
        return Decision(approved, "weighted", yes, no, threshold, "weighted_accept" if approved else "weighted_reject")

    def unanimous(self, votes: list[Vote]) -> Decision:
        approved = bool(votes) and all(vote.accepted for vote in votes)
        yes = sum(1 for vote in votes if vote.accepted)
        no = len(votes) - yes
        return Decision(approved, "unanimous", yes, no, 1.0, "unanimous_accept" if approved else "unanimous_reject")
