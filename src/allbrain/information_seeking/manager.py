from __future__ import annotations

from allbrain.information_seeking.evaluator import InformationSeekingEvaluator
from allbrain.information_seeking.models import InformationPlan
from allbrain.information_seeking.planner import InformationPlanner
from allbrain.uncertainty.models import KnowledgeGap


class InformationSeekingManager:
    def __init__(
        self,
        *,
        evaluator: InformationSeekingEvaluator | None = None,
        planner: InformationPlanner | None = None,
    ) -> None:
        self.evaluator = evaluator or InformationSeekingEvaluator()
        self.planner = planner or InformationPlanner(self.evaluator)

    def analyze(
        self,
        gaps: list[KnowledgeGap],
        *,
        analysis_id=None,
    ) -> InformationPlan:
        needs = self.planner.needs_from_gaps(gaps)
        return self.planner.plan(needs, analysis_id=analysis_id)
