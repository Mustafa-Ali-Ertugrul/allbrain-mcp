from __future__ import annotations

from allbrain.domains.governance.mitigation_learning.model import (
    MIN_USES_FOR_OPTIMIZER,
    StrategyStats,
)


def _score(stats: StrategyStats) -> float:
    return stats.success_rate * 0.6 + stats.avg_effectiveness * 0.4


class StrategyOptimizer:
    """Recommends the best strategy based on learned history.

    Only activates after MIN_USES_FOR_OPTIMIZER (4) observations.
    Falls back to the default strategy when:
      - No history exists
      - All learned strategies are disabled
      - Fewer than MIN_USES_FOR_OPTIMIZER observations
    """

    @staticmethod
    def recommend(
        *,
        fault_type: str,
        signal_type: str,
        default_strategy: str,
        all_stats: dict[tuple[str, str, str], StrategyStats],
    ) -> str:
        """Return the best strategy for a given fault_type/signal_type.

        Falls back to default_strategy if no learned data exists.
        """
        candidates = [
            s
            for s in all_stats.values()
            if s.fault_type == fault_type
            and s.signal_type == signal_type
            and not s.disabled
            and s.total_uses >= MIN_USES_FOR_OPTIMIZER
        ]

        if not candidates:
            return default_strategy

        candidates.sort(key=_score, reverse=True)
        best_score = _score(candidates[0])

        if best_score <= 0.0:
            return default_strategy

        return candidates[0].strategy
