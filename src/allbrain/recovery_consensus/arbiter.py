from __future__ import annotations

import hashlib
from typing import Any

from allbrain.recovery_consensus.model import (
    CandidateStrategy,
    RecoveryDecision,
    ScoredCandidate,
    CONSENSUS_MIN_RATIO,
)


class Arbiter:
    """Selects the best recovery strategy from scored candidates.

    The candidate with the highest score is selected. If its score
    represents >= min_consensus_ratio of total score, consensus is
    considered reached.
    """

    def __init__(self, min_consensus_ratio: float = CONSENSUS_MIN_RATIO) -> None:
        self._min_consensus_ratio = min_consensus_ratio

    def arbitrate(
        self,
        candidates: list[ScoredCandidate],
        *,
        fault_id: str,
    ) -> RecoveryDecision:
        """Arbitrate among scored candidates.

        Args:
            candidates: Scored candidates (must be non-empty).
            fault_id: The fault being decided on.

        Returns:
            A RecoveryDecision with the selected strategy.
        """
        if not candidates:
            return RecoveryDecision(
                selected_strategy="retry",
                consensus_score=0.0,
                rejected_strategies=(),
                reason="no_candidates_fallback_to_retry",
                fault_id=fault_id,
                decision_id=self._stable_decision_id(fault_id, 0),
                candidate_count=0,
            )

        # Sort by score descending (should already be sorted)
        sorted_candidates = sorted(candidates, key=lambda s: -s.score)

        winner = sorted_candidates[0]
        total_score = sum(s.score for s in sorted_candidates)
        consensus_score = winner.score / total_score if total_score > 0 else 0.0
        consensus_score = max(0.0, min(1.0, consensus_score))

        consensus_reached = consensus_score >= self._min_consensus_ratio

        rejected = tuple(
            s.candidate.strategy for s in sorted_candidates[1:]
        )

        if consensus_reached:
            reason = (
                f"selected={winner.candidate.strategy} "
                f"score={winner.score:.3f} "
                f"consensus={consensus_score:.3f} "
                f"rejected={rejected}"
            )
        else:
            reason = (
                f"low_consensus: winner={winner.candidate.strategy} "
                f"score={winner.score:.3f} "
                f"consensus={consensus_score:.3f} "
                f"(below threshold {self._min_consensus_ratio})"
            )

        decision_id = self._stable_decision_id(fault_id, len(sorted_candidates))

        return RecoveryDecision(
            selected_strategy=winner.candidate.strategy,
            consensus_score=consensus_score,
            rejected_strategies=rejected,
            reason=reason,
            fault_id=fault_id,
            decision_id=decision_id,
            candidate_count=len(sorted_candidates),
        )

    @staticmethod
    def _stable_decision_id(fault_id: str, candidate_count: int) -> str:
        raw = f"decision::{fault_id}::{candidate_count}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
