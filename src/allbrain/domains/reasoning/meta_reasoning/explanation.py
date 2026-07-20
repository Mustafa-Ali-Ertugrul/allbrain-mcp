from __future__ import annotations

from allbrain.domains.reasoning.foresight.models import FuturePlan
from allbrain.domains.reasoning.meta_reasoning.models import (
    ConfidenceEstimate,
    DecisionExplanation,
    DecisionReason,
    RejectedAlternative,
)


class ExplanationGenerator:
    def build(
        self,
        selected_plan: FuturePlan,
        reasons: list[DecisionReason],
        rejected: list[RejectedAlternative],
        confidence: ConfidenceEstimate,
        foresight_result,
    ) -> DecisionExplanation:
        return DecisionExplanation(
            selected_option=" -> ".join(selected_plan.actions),
            confidence=confidence,
            reasons=reasons,
            rejected=rejected,
            template_version=1,
            analysis_id=foresight_result.analysis_id,
        )
