from __future__ import annotations

from uuid6 import uuid7

from allbrain.domains.analysis.world import PredictionBridge, SimulationBridge, StateTransitionBridge, WorldState
from allbrain.domains.reasoning.scenarios.evaluator import ScenarioEvaluator
from allbrain.domains.reasoning.scenarios.generator import ScenarioGenerator
from allbrain.domains.reasoning.scenarios.models import SCENARIO_TEMPLATE_VERSION, ScenarioAnalysis, ScenarioResult
from allbrain.domains.reasoning.scenarios.ranking import ScenarioRanker


def _default_simulator() -> SimulationBridge:
    return SimulationBridge(StateTransitionBridge(), PredictionBridge())


class ScenarioEngine:
    def __init__(
        self,
        generator: ScenarioGenerator | None = None,
        evaluator: ScenarioEvaluator | None = None,
        ranker: ScenarioRanker | None = None,
    ) -> None:
        self.generator = generator or ScenarioGenerator()
        self.evaluator = evaluator or ScenarioEvaluator(_default_simulator())
        self.ranker = ranker or ScenarioRanker()

    def analyze(self, state: WorldState, action: str, *, limit: int | None = None) -> ScenarioAnalysis:
        templates = self.generator.defaults()
        if limit is not None and limit >= 0:
            templates = templates[:limit]
        results: list[ScenarioResult] = []
        for template in templates:
            results.append(self.evaluator.evaluate(state, action, template))
        selected = self.ranker.select(results)
        metrics = self.ranker.metrics(results)
        return ScenarioAnalysis(
            analysis_id=uuid7(),
            action=action,
            best_case=selected["best_case"],
            expected_case=selected["expected_case"],
            worst_case=selected["worst_case"],
            safest_case=selected["safest_case"],
            prediction_spread=metrics["prediction_spread"],
            risk_volatility=metrics["risk_volatility"],
            uncertainty=metrics["uncertainty"],
            confidence_total=metrics["confidence_total"],
            template_version=SCENARIO_TEMPLATE_VERSION,
            results=list(results),
        )

    def evaluate_custom(self, state: WorldState, action: str, scenarios: list[dict]) -> ScenarioAnalysis:
        templates = self.generator.from_specs(scenarios)
        results: list[ScenarioResult] = []
        for template in templates:
            results.append(self.evaluator.evaluate(state, action, template))
        selected = self.ranker.select(results)
        metrics = self.ranker.metrics(results)
        return ScenarioAnalysis(
            analysis_id=uuid7(),
            action=action,
            best_case=selected["best_case"],
            expected_case=selected["expected_case"],
            worst_case=selected["worst_case"],
            safest_case=selected["safest_case"],
            prediction_spread=metrics["prediction_spread"],
            risk_volatility=metrics["risk_volatility"],
            uncertainty=metrics["uncertainty"],
            confidence_total=metrics["confidence_total"],
            template_version=templates[0].template_version if templates else SCENARIO_TEMPLATE_VERSION,
            results=list(results),
        )
