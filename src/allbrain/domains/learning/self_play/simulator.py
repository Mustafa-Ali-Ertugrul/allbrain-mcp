from __future__ import annotations

from allbrain.mitigation_learning.model import StrategyStats
from allbrain.domains.learning.self_play.model import SELF_PLAY_SIM_WEIGHT_CAP, MatchResult


class Simulator:
    """Deterministic outcome simulator for self-play.

    Projects a winner using StrategyStats — no randomness.
    Winner = higher composite score.

    Composite = 0.50 * success_rate + 0.25 * avg_effectiveness - 0.25 * disabled_penalty
    """

    def simulate(
        self,
        fault_type: str,
        policy_a: str,
        policy_b: str,
        all_stats: dict[tuple[str, str, str], StrategyStats],
    ) -> MatchResult:
        key_a = (fault_type, fault_type, policy_a)
        key_b = (fault_type, fault_type, policy_b)
        stats_a = all_stats.get(key_a)
        stats_b = all_stats.get(key_b)

        score_a = self._composite(stats_a)
        score_b = self._composite(stats_b)

        gap = abs(score_a - score_b)
        confidence = min(1.0, max(0.05, gap * 2.0))

        winner = policy_a if score_a >= score_b else policy_b

        return MatchResult(
            policy_a=policy_a,
            policy_b=policy_b,
            winner=winner,
            score_a=score_a,
            score_b=score_b,
            confidence=confidence,
            fault_type=fault_type,
        )

    @staticmethod
    def _composite(stats: StrategyStats | None) -> float:
        if stats is None:
            return 0.3
        penalty = 0.5 if stats.disabled else 0.0
        return min(
            1.0,
            max(
                0.0,
                SELF_PLAY_SIM_WEIGHT_CAP
                * (0.50 * stats.success_rate + 0.25 * stats.avg_effectiveness - 0.25 * penalty),
            ),
        )
