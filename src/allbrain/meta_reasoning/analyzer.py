from __future__ import annotations

from allbrain.foresight.models import FuturePlan
from allbrain.meta_reasoning.models import DecisionReason


class DecisionAnalyzer:
    def analyze(
        self,
        selected_plan: FuturePlan,
        candidates: list[FuturePlan],
        foresight_result,
        *,
        historical_success: float | None = None,
    ) -> list[DecisionReason]:
        if candidates:
            avg_success = sum(p.predicted_success for p in candidates) / len(candidates)
            avg_risk = sum(p.cumulative_risk for p in candidates) / len(candidates)
        else:
            avg_success = 0.0
            avg_risk = 0.0
        success_delta = round(selected_plan.predicted_success - avg_success, 6)
        risk_delta = round(avg_risk - selected_plan.cumulative_risk, 6)
        horizon_factor = round(1.0 / max(1, selected_plan.horizon), 6)
        hist = historical_success if historical_success is not None else 0.0
        return [
            DecisionReason(
                factor="predicted_success",
                contribution=success_delta,
                explanation=(
                    f"Selected plan success {selected_plan.predicted_success:.2f} "
                    f"vs average {avg_success:.2f}"
                ),
            ),
            DecisionReason(
                factor="cumulative_risk",
                contribution=risk_delta,
                explanation=(
                    f"Selected plan risk {selected_plan.cumulative_risk:.2f} "
                    f"vs average {avg_risk:.2f}"
                ),
            ),
            DecisionReason(
                factor="horizon",
                contribution=horizon_factor,
                explanation=f"Plan depth is {selected_plan.horizon} steps",
            ),
            DecisionReason(
                factor="historical_success",
                contribution=round(hist, 6),
                explanation=f"Historical success rate: {hist:.2f}",
            ),
        ]
