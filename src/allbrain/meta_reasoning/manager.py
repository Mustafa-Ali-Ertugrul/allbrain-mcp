from __future__ import annotations

from allbrain.foresight.models import FuturePlan
from allbrain.meta_reasoning.analyzer import DecisionAnalyzer
from allbrain.meta_reasoning.confidence import ConfidenceEngine
from allbrain.meta_reasoning.explanation import ExplanationGenerator
from allbrain.meta_reasoning.models import DecisionExplanation
from allbrain.meta_reasoning.rejection import RejectionAnalyzer


class MetaReasoningManager:
    def __init__(self) -> None:
        self.analyzer = DecisionAnalyzer()
        self.confidence_engine = ConfidenceEngine()
        self.rejection_analyzer = RejectionAnalyzer()
        self.explanation_generator = ExplanationGenerator()

    def explain(
        self,
        selected_plan: FuturePlan,
        candidates: list[FuturePlan],
        foresight_result,
    ) -> DecisionExplanation:
        reasons = self.analyzer.analyze(selected_plan, candidates, foresight_result)
        rejected = self.rejection_analyzer.analyze(selected_plan, candidates)
        confidence = self.confidence_engine.estimate(selected_plan, foresight_result)
        return self.explanation_generator.build(
            selected_plan=selected_plan,
            reasons=reasons,
            rejected=rejected,
            confidence=confidence,
            foresight_result=foresight_result,
        )
