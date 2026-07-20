from __future__ import annotations

from typing import TYPE_CHECKING

from allbrain.recovery_consensus.model import (
    DEFAULT_CONFIDENCE_WEIGHT,
    DEFAULT_RISK_WEIGHT,
    DEFAULT_SUCCESS_WEIGHT,
    CandidateStrategy,
    ScoredCandidate,
)

if TYPE_CHECKING:
    from allbrain.domains.analysis.failure_memory.manager import FailureMemoryManager


class Evaluator:
    """Scores candidate recovery strategies.

    Uses the arbiter formula to compute a score per candidate:
        score = success * success_weight + confidence * confidence_weight - risk * risk_weight

    Recent fault history reduces success estimates to penalize
    strategies that have been failing repeatedly.

    When memory and bias_weight are provided, historical success
    rates from failure memory are blended into each candidate's score:
        final = current*(1-bias) + historical*bias
    """

    def __init__(
        self,
        success_weight: float = DEFAULT_SUCCESS_WEIGHT,
        confidence_weight: float = DEFAULT_CONFIDENCE_WEIGHT,
        risk_weight: float = DEFAULT_RISK_WEIGHT,
    ) -> None:
        self._success_weight = success_weight
        self._confidence_weight = confidence_weight
        self._risk_weight = risk_weight

    def evaluate(
        self,
        candidates: list[CandidateStrategy],
        *,
        recent_failures: int = 0,
        memory: FailureMemoryManager | None = None,
        bias_weight: float = 0.0,
        fault_type: str = "",
    ) -> list[ScoredCandidate]:
        """Score and rank candidates.

        Args:
            candidates: Unscored candidate strategies.
            recent_failures: Number of recent recovery failures.
                Used to reduce success estimates.
            memory: Optional FailureMemoryManager for historical bias.
            bias_weight: Weight of historical bias [0,1]. 0 means no bias.
            fault_type: Fault type used as memory lookup key.

        Returns:
            ScoredCandidate list sorted by score descending.
        """
        if not candidates:
            return []

        apply_bias = memory is not None and bias_weight > 0.0 and fault_type

        scored: list[tuple[int, ScoredCandidate]] = []
        for idx, c in enumerate(candidates):
            success = c.estimated_success

            # Adjust success downward if recent failures are high
            if recent_failures > 10:
                success *= 0.70
            elif recent_failures > 6:
                success *= 0.80
            elif recent_failures > 3:
                success *= 0.90

            success = max(0.0, min(1.0, success))
            confidence = max(0.0, min(1.0, c.confidence))
            risk = max(0.0, min(1.0, c.risk))

            score = success * self._success_weight + confidence * self._confidence_weight - risk * self._risk_weight
            score = max(0.0, min(1.0, score))

            # Blend historical bias if memory is available
            if apply_bias:
                historical = memory.compute_bias(fault_type, c.strategy)
                historical = max(0.0, min(1.0, historical))
                score = score * (1.0 - bias_weight) + historical * bias_weight
                score = max(0.0, min(1.0, score))

            scored.append(
                (
                    idx,
                    ScoredCandidate(
                        candidate=c,
                        score=score,
                        rank=0,
                    ),
                )
            )

        # Sort by score descending, stable tiebreak by input order
        scored.sort(key=lambda pair: (-pair[1].score, pair[0]))

        # Assign ranks
        result: list[ScoredCandidate] = []
        for i, (_, s) in enumerate(scored):
            result.append(
                ScoredCandidate(
                    candidate=s.candidate,
                    score=s.score,
                    rank=i + 1,
                )
            )

        return result
