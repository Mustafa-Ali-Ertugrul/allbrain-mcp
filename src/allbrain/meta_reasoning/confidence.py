from __future__ import annotations

from allbrain.foresight.models import FuturePlan
from allbrain.meta_reasoning.models import ConfidenceEstimate


HISTORICAL_SUCCESS_DEFAULT = 0.7


class ConfidenceEngine:
    def estimate(self, selected_plan: FuturePlan, foresight_result) -> ConfidenceEstimate:
        foresight_score = selected_plan.predicted_success
        sample_confidence = selected_plan.confidence
        historical_success = HISTORICAL_SUCCESS_DEFAULT
        confidence = round(
            historical_success * 0.4 + foresight_score * 0.4 + sample_confidence * 0.2,
            6,
        )
        return ConfidenceEstimate(
            confidence=confidence,
            evidence_count=len(foresight_result.plans),
            uncertainty=round(1.0 - confidence, 6),
        )
