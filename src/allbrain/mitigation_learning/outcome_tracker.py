from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from allbrain.mitigation_learning.model import (
    STRATEGY_BASE_EFFECTIVENESS,
    OutcomeRecord,
)

# imported lazily inside measure() to avoid circular import


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


OutcomeProvider = Callable[[str, float, float], tuple[float, bool, float]]


class OutcomeTracker:
    """Measures system state after mitigation execution.

    Default: uses a deterministic strategy effectiveness simulation
    table as baseline reference. Can accept an injected outcome
    provider for production or test scenarios.
    """

    def __init__(self, outcome_provider: OutcomeProvider | None = None) -> None:
        self._provider = outcome_provider

    def set_provider(self, provider: OutcomeProvider | None) -> None:
        self._provider = provider

    def measure(
        self,
        *,
        fault_id: str,
        fault_type: str,
        plan_id: str,
        strategy: str,
        pre_risk: float,
        urgency: float,
        timestamp: float = 0.0,
    ) -> OutcomeRecord:
        """Measure post-execution state and return OutcomeRecord."""
        if self._provider is not None:
            post_risk, failure_prevented, stability_delta = self._provider(
                strategy,
                pre_risk,
                urgency,
            )
        else:
            base_eff = STRATEGY_BASE_EFFECTIVENESS.get(strategy, 0.30)
            reduction = base_eff * urgency
            post_risk = _clamp(pre_risk * (1.0 - reduction))
            from allbrain.predictive_failure.model import RISK_THRESHOLD_FAILURE
            failure_prevented = post_risk < RISK_THRESHOLD_FAILURE
            stability_delta = _clamp(pre_risk - post_risk)

        risk_delta = pre_risk - post_risk
        outcome_id = hashlib.sha256(f"{fault_id}|{plan_id}|{strategy}|{pre_risk:.6f}".encode()).hexdigest()[:16]

        return OutcomeRecord(
            outcome_id=outcome_id,
            fault_id=fault_id,
            fault_type=fault_type,
            plan_id=plan_id,
            strategy=strategy,
            pre_risk=pre_risk,
            post_risk=post_risk,
            risk_delta=risk_delta,
            failure_prevented=failure_prevented,
            stability_delta=stability_delta,
            timestamp=timestamp,
        )
