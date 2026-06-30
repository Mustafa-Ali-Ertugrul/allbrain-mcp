from __future__ import annotations

from allbrain.mitigation_learning.model import StrategyStats
from allbrain.objective_system.model import (
    EFFICIENCY_CYCLE_WEIGHT,
    EFFICIENCY_PREVENTION_WEIGHT,
    FAULT_TYPE_SAFETY_THRESHOLDS,
    ObjectiveResult,
    ObjectiveSnapshot,
)


class Objective:
    """Computes scalar objective metrics from StrategyStats.

    Safety     = 1.0 - avg_failure_rate (1-P(failure))
    Stability  = existing stability_score from policy evaluation
    Success    = success_rate directly from stats
    Efficiency = 0.6 * prevention_rate + 0.4 * cycle_efficiency
    """

    @staticmethod
    def compute(
        fault_type: str,
        strategy: str,
        stats: StrategyStats | None,
        stability_score: float,
        cycle_count: int,
    ) -> ObjectiveResult:
        if stats is not None and stats.total_uses > 0:
            safety = stats.success_rate
            stability_metric = stability_score
            success_metric = stats.success_rate
            prevention_rate = stats.success_rate
            cycle_eff = min(1.0, 1.0 / max(1, cycle_count))
            efficiency_metric = EFFICIENCY_PREVENTION_WEIGHT * prevention_rate + EFFICIENCY_CYCLE_WEIGHT * cycle_eff
        else:
            safety = 0.5
            stability_metric = stability_score
            success_metric = 0.5
            efficiency_metric = 0.5

        threshold = FAULT_TYPE_SAFETY_THRESHOLDS.get(fault_type, 0.50)
        safety_pass = safety >= threshold

        return ObjectiveResult(
            fault_type=fault_type, safety=safety, stability=stability_metric,
            success=success_metric, efficiency=efficiency_metric,
            safety_pass=safety_pass,
            normalized={
                "safety": safety, "stability": stability_metric,
                "success": success_metric, "efficiency": efficiency_metric,
            },
        )

    @staticmethod
    def snapshot(result: ObjectiveResult) -> ObjectiveSnapshot:
        return ObjectiveSnapshot(
            fault_type=result.fault_type, safety=result.safety,
            stability=result.stability, success=result.success,
            efficiency=result.efficiency,
        )
