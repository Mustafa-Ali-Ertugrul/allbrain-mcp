from __future__ import annotations

import hashlib
from typing import Any

from allbrain.mitigation_learning.model import (
    LearningRecord,
    StrategyStats,
    PolicyVersion,
    LEARNING_EMA_ALPHA,
    MIN_USES_FOR_DISABLE,
    DISABLE_SUCCESS_RATE_THRESHOLD,
)


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class LearningEngine:
    """Updates strategy ratings based on measured outcomes.

    Uses EMA (exponential moving average) to track effectiveness.
    Disables strategies that consistently fail below threshold.
    """

    def __init__(self) -> None:
        self._stats: dict[tuple[str, str, str], StrategyStats] = {}

    @property
    def stats(self) -> dict[tuple[str, str, str], StrategyStats]:
        return self._stats

    def update(
        self,
        record: LearningRecord,
    ) -> tuple[StrategyStats | None, PolicyVersion | None]:
        """Update strategy stats from a learning record.

        Returns (strategy_updated_stats, policy_update_if_any).
        policy_update is None — call policy store separately.
        """
        key = (record.fault_type, record.signal_type, record.strategy)
        stats = self._stats.get(key)

        if stats is None:
            stats = StrategyStats(
                fault_type=record.fault_type,
                signal_type=record.signal_type,
                strategy=record.strategy,
            )
            self._stats[key] = stats

        stats.total_uses += 1
        if record.success:
            stats.successes += 1
        else:
            stats.failures += 1

        stats.avg_effectiveness = (
            stats.avg_effectiveness * (1.0 - LEARNING_EMA_ALPHA)
            + record.effectiveness_score * LEARNING_EMA_ALPHA
        )
        stats.success_rate = stats.successes / stats.total_uses
        stats.last_used_at = record.occurred_at

        if (
            stats.total_uses >= MIN_USES_FOR_DISABLE
            and stats.success_rate < DISABLE_SUCCESS_RATE_THRESHOLD
        ):
            stats.disabled = True

        return stats, None

    @staticmethod
    def compute_effectiveness(risk_delta: float, pre_risk: float) -> float:
        """Compute effectiveness score [-1, 1]."""
        if pre_risk <= 0.0:
            return 0.0
        return _clamp(risk_delta / pre_risk)

    @staticmethod
    def make_learning_record(
        *,
        fault_id: str,
        fault_type: str,
        signal_type: str,
        strategy: str,
        risk_delta: float,
        pre_risk: float,
        success: bool,
        occurred_at: float = 0.0,
        policy_version: int = 0,
    ) -> LearningRecord:
        effectiveness = LearningEngine.compute_effectiveness(risk_delta, pre_risk)
        learning_id = hashlib.sha256(
            f"{fault_id}|{strategy}|{occurred_at:.6f}".encode()
        ).hexdigest()[:16]
        return LearningRecord(
            learning_id=learning_id,
            fault_id=fault_id,
            fault_type=fault_type,
            signal_type=signal_type,
            strategy=strategy,
            effectiveness_score=effectiveness,
            success=success,
            occurred_at=occurred_at,
            policy_version=policy_version,
        )