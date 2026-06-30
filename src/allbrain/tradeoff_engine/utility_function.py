from __future__ import annotations

from allbrain.objective_system.model import (
    OBJECTIVE_PRIORITY_DEFAULTS,
    ObjectivePriority,
    ObjectiveResult,
    ObjectiveWeights,
)
from allbrain.tradeoff_engine.model import UTILITY_SAFETY_MULTIPLIER, UtilityResult


class UtilityFunction:
    """Computes utility from objective metrics and weights.

    CRITICAL objectives: must pass (safety_pass == True), else utility = -inf
    IMPORTANT objectives: contribute to utility with amplified safety
    OPTIONAL objectives: contribute to utility normally
    """

    @staticmethod
    def compute(result: ObjectiveResult, weights: ObjectiveWeights, policy_id: str, strategy: str) -> UtilityResult:
        if not result.safety_pass:
            return UtilityResult(policy_id=policy_id, strategy=strategy, fault_type=result.fault_type,
                utility=-1e9, safety=result.safety, stability=result.stability,
                success=result.success, efficiency=result.efficiency, safety_pass=False)

        u = 0.0
        for name, val in [("safety", result.safety), ("stability", result.stability),
                           ("success", result.success), ("efficiency", result.efficiency)]:
            prio = OBJECTIVE_PRIORITY_DEFAULTS.get(name, ObjectivePriority.OPTIONAL)
            w = getattr(weights, name)
            if prio == ObjectivePriority.CRITICAL:
                u += w * val * UTILITY_SAFETY_MULTIPLIER
            else:
                u += w * val

        return UtilityResult(policy_id=policy_id, strategy=strategy, fault_type=result.fault_type,
            utility=min(1.0, u), safety=result.safety, stability=result.stability,
            success=result.success, efficiency=result.efficiency, safety_pass=True)
