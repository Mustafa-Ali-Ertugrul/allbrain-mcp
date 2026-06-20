from __future__ import annotations

from allbrain.foresight.models import FuturePlan


class PlanRanker:
    def select(self, plans: list[FuturePlan]) -> dict[str, FuturePlan]:
        best = max(plans, key=lambda item: item.predicted_success)
        safest = min(plans, key=lambda item: item.cumulative_risk)
        fastest = min(plans, key=lambda item: item.horizon)
        sorted_by_score = sorted(plans, key=lambda item: item.predicted_success - item.cumulative_risk)
        median_index = len(sorted_by_score) // 2
        expected = sorted_by_score[median_index]
        return {
            "best_plan": best,
            "safest_plan": safest,
            "fastest_plan": fastest,
            "expected_plan": expected,
        }

    def metrics(self, plans: list[FuturePlan]) -> dict[str, float]:
        if not plans:
            return {
                "plan_spread": 0.0,
                "strategy_uncertainty": 1.0,
                "horizon_risk": 0.0,
            }
        successes = [item.predicted_success for item in plans]
        confidences = [item.confidence for item in plans]
        sorted_by_score = sorted(plans, key=lambda item: item.predicted_success - item.cumulative_risk)
        median_index = len(sorted_by_score) // 2
        expected_plan = sorted_by_score[median_index]
        return {
            "plan_spread": round(max(successes) - min(successes), 6),
            "strategy_uncertainty": round(1.0 - sum(c * p for c, p in zip(confidences, successes)), 6),
            "horizon_risk": expected_plan.cumulative_risk,
        }
