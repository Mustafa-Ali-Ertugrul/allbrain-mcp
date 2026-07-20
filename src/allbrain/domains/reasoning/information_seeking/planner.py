from __future__ import annotations

from uuid6 import uuid7

from allbrain.domains.reasoning.information_seeking.evaluator import InformationSeekingEvaluator
from allbrain.domains.reasoning.information_seeking.models import (
    INFORMATION_SEEKING_TEMPLATE_VERSION,
    InformationAction,
    InformationNeed,
    InformationPlan,
)
from allbrain.domains.reasoning.uncertainty.models import KnowledgeGap


class InformationPlanner:
    def __init__(self, evaluator: InformationSeekingEvaluator | None = None) -> None:
        self.evaluator = evaluator or InformationSeekingEvaluator()

    def needs_from_gaps(self, gaps: list[KnowledgeGap]) -> list[InformationNeed]:
        return [
            InformationNeed(
                topic=gap.topic,
                expected_gain=round(1.0 - gap.severity, 6),
                cost=0.1 if gap.recoverable else 0.3,
                priority=0.0,
            )
            for gap in gaps
        ]

    def plan(
        self,
        needs: list[InformationNeed],
        *,
        analysis_id=None,
    ) -> InformationPlan:
        if not needs:
            return InformationPlan(
                analysis_id=analysis_id or uuid7(),
                needs=[],
                selected_action=None,
                expected_voi=0.0,
                rationale="no information needs detected",
                template_version=INFORMATION_SEEKING_TEMPLATE_VERSION,
            )
        candidates: list[tuple[InformationAction, float, float, float]] = []
        for action in InformationAction:
            gain, cost, voi = self.evaluator.evaluate(action, needs)
            candidates.append((action, gain, cost, voi))
        best_action, best_gain, best_cost, best_voi = max(candidates, key=lambda item: item[3])
        needs_with_priority = [
            InformationNeed(
                topic=n.topic,
                expected_gain=n.expected_gain,
                cost=n.cost,
                priority=max(0.0, round(n.expected_gain - n.cost, 6)),
            )
            for n in needs
        ]
        rationale = f"selected {best_action.value} with VOI {best_voi} for {len(needs)} need(s)"
        return InformationPlan(
            analysis_id=analysis_id or uuid7(),
            needs=needs_with_priority,
            selected_action=best_action,
            expected_voi=best_voi,
            rationale=rationale,
            template_version=INFORMATION_SEEKING_TEMPLATE_VERSION,
        )
