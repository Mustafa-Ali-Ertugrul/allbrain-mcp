from __future__ import annotations

from allbrain.domains.reasoning.foresight.models import FuturePlan
from allbrain.domains.reasoning.meta_reasoning.models import RejectedAlternative


class RejectionAnalyzer:
    def analyze(
        self,
        selected_plan: FuturePlan,
        candidates: list[FuturePlan],
    ) -> list[RejectedAlternative]:
        rejected: list[RejectedAlternative] = []
        selected_score = selected_plan.predicted_success - selected_plan.cumulative_risk
        for candidate in candidates:
            if list(candidate.actions) == list(selected_plan.actions):
                continue
            candidate_score = candidate.predicted_success - candidate.cumulative_risk
            score_gap = round(selected_score - candidate_score, 6)
            reasons: list[str] = []
            if candidate.predicted_success < selected_plan.predicted_success:
                reasons.append("lower_score")
            if candidate.cumulative_risk > selected_plan.cumulative_risk:
                reasons.append("higher_risk")
            if candidate.horizon > 5:
                reasons.append("insufficient_evidence")
            reason = ", ".join(reasons) if reasons else "lower_combined_score"
            rejected.append(
                RejectedAlternative(
                    option=" -> ".join(candidate.actions),
                    reason=reason,
                    score_gap=score_gap,
                )
            )
        return rejected
