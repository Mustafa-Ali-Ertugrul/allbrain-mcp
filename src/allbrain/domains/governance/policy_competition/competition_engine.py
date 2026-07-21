from __future__ import annotations

from allbrain.domains.governance.mitigation_learning.model import StrategyStats
from allbrain.domains.governance.policy_competition.evaluator import PolicyEvaluator
from allbrain.domains.governance.policy_competition.model import (
    COMPETITION_MIN_CONFIDENCE,
    CompetitionResult,
    PolicyCandidate,
)


class CompetitionEngine:
    """Runs policy competition: given candidates, scores them and selects the winner.

    Winner = argmax(score).
    Confidence = score(winner) - score(runner_up).
    """

    def __init__(self) -> None:
        self._evaluator = PolicyEvaluator()

    def compete(
        self,
        candidates: list[PolicyCandidate],
        all_stats: dict[tuple[str, str, str], StrategyStats],
    ) -> CompetitionResult | None:
        if not candidates:
            return None

        scored = self._evaluator.evaluate(candidates, all_stats)
        if not scored:
            return None

        scored.sort(key=lambda s: s.score, reverse=True)
        winner = scored[0]
        runner_up_score = scored[1].score if len(scored) > 1 else 0.0
        confidence = max(COMPETITION_MIN_CONFIDENCE, winner.score - runner_up_score)
        score_map = {s.candidate.policy_id: s.score for s in scored}

        return CompetitionResult(
            winner=winner,
            score_map=score_map,
            confidence=confidence,
        )
