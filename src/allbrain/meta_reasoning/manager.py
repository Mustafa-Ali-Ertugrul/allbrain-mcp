from __future__ import annotations

from typing import Any

from allbrain.foresight.models import FuturePlan
from allbrain.meta_reasoning.analyzer import DecisionAnalyzer
from allbrain.meta_reasoning.confidence import ConfidenceEngine
from allbrain.meta_reasoning.explanation import ExplanationGenerator
from allbrain.meta_reasoning.models import DecisionExplanation
from allbrain.meta_reasoning.rejection import RejectionAnalyzer
from allbrain.uncertainty.calibration import observed_success_rate

HISTORICAL_SUCCESS_FALLBACK = 0.7


class MetaReasoningManager:
    def __init__(self, *, calibration_events: list[Any] | None = None) -> None:
        self.analyzer = DecisionAnalyzer()
        self.confidence_engine = ConfidenceEngine()
        self.rejection_analyzer = RejectionAnalyzer()
        self.explanation_generator = ExplanationGenerator()
        self._calibration_events = calibration_events or []

    def explain(
        self,
        selected_plan: FuturePlan,
        candidates: list[FuturePlan],
        foresight_result,
        *,
        historical_success: float | None = None,
    ) -> DecisionExplanation:
        reasons = self.analyzer.analyze(selected_plan, candidates, foresight_result, historical_success=historical_success)
        rejected = self.rejection_analyzer.analyze(selected_plan, candidates)
        if historical_success is None:
            historical_success = (
                observed_success_rate(self._calibration_events)
                if self._calibration_events
                else HISTORICAL_SUCCESS_FALLBACK
            )
        confidence = self.confidence_engine.estimate(selected_plan, foresight_result, historical_success)
        return self.explanation_generator.build(
            selected_plan=selected_plan,
            reasons=reasons,
            rejected=rejected,
            confidence=confidence,
            foresight_result=foresight_result,
        )
