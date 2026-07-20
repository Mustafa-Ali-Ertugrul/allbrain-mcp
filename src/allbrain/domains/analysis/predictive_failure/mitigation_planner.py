from __future__ import annotations

import hashlib

from allbrain.domains.analysis.predictive_failure.model import (
    DEFAULT_MITIGATION,
    LEVEL_FAILURE,
    MITIGATION_STRATEGIES,
    STRATEGY_URGENCY,
    FailurePrediction,
    MitigationPlan,
)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class MitigationPlanner:
    """Plans proactive mitigations based on failure predictions.

    Maps the top signal type to a mitigation strategy, computes
    urgency and expected risk reduction. Only plans at FAILURE level.
    """

    @staticmethod
    def plan(prediction: FailurePrediction) -> MitigationPlan | None:
        """Create a MitigationPlan, or None if below FAILURE threshold."""
        if prediction.level != LEVEL_FAILURE:
            return None

        signal_type = prediction.top_signals[0] if prediction.top_signals else "unknown"
        strategy = MITIGATION_STRATEGIES.get(signal_type, DEFAULT_MITIGATION)
        urgency = STRATEGY_URGENCY.get(strategy, 0.30)
        expected_reduction = _clamp(urgency * prediction.probability)

        plan_id = hashlib.sha256(f"{prediction.fault_id}::{strategy}".encode()).hexdigest()[:16]

        return MitigationPlan(
            plan_id=plan_id,
            fault_id=prediction.fault_id,
            fault_type=prediction.fault_type,
            strategy=strategy,
            urgency=urgency,
            expected_risk_reduction=expected_reduction,
        )
