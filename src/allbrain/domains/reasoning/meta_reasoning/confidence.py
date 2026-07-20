from __future__ import annotations

from allbrain.domains.reasoning.foresight.models import FuturePlan
from allbrain.domains.reasoning.meta_reasoning.models import ConfidenceEstimate


class ConfidenceEngine:
    def estimate(self, selected_plan: FuturePlan, foresight_result, historical_success: float) -> ConfidenceEstimate:
        foresight_score = selected_plan.predicted_success
        sample_confidence = selected_plan.confidence
        confidence = round(
            historical_success * 0.4 + foresight_score * 0.4 + sample_confidence * 0.2,
            6,
        )
        return ConfidenceEstimate(
            confidence=confidence,
            evidence_count=len(foresight_result.plans),
            uncertainty=round(1.0 - confidence, 6),
        )
