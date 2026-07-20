from __future__ import annotations

from uuid6 import uuid7

from allbrain.domains.analysis.world import PredictionBridge, SimulationBridge, StateTransitionBridge, WorldState
from allbrain.domains.reasoning.foresight.evaluator import PlanEvaluator
from allbrain.domains.reasoning.foresight.models import FORESIGHT_TEMPLATE_VERSION, ForesightAnalysis, FuturePlan
from allbrain.domains.reasoning.foresight.planner import ActionPlanner
from allbrain.domains.reasoning.foresight.ranking import PlanRanker
from allbrain.domains.reasoning.foresight.simulator import MultiStepSimulator

_PLAN_CONFIDENCE = (0.35, 0.35, 0.20, 0.10)
_PLAN_ROLES = ("best", "expected", "safest", "fastest")


def _default_simulator() -> SimulationBridge:
    return SimulationBridge(StateTransitionBridge(), PredictionBridge())


def _empty_plan(action: str) -> FuturePlan:
    return FuturePlan(
        actions=[],
        predicted_success=0.0,
        cumulative_risk=0.0,
        cumulative_cost=0.0,
        horizon=0,
        confidence=0.0,
        step_states=[],
    )


class ForesightEngine:
    def __init__(
        self,
        planner: ActionPlanner | None = None,
        simulator: MultiStepSimulator | None = None,
        evaluator: PlanEvaluator | None = None,
        ranker: PlanRanker | None = None,
        *,
        max_horizon: int = 5,
        confidence_decay: float = 0.90,
    ) -> None:
        self.planner = planner or ActionPlanner()
        sim = simulator or MultiStepSimulator(_default_simulator(), confidence_decay=confidence_decay)
        self.simulator = sim
        self.evaluator = evaluator or PlanEvaluator(sim, max_horizon=max_horizon, confidence_decay=confidence_decay)
        self.ranker = ranker or PlanRanker()
        self.max_horizon = max_horizon

    def analyze(self, state: WorldState, action: str, *, limit: int = 5) -> ForesightAnalysis:
        plans_list = self.planner.generate(action)[:limit]
        if not plans_list:
            empty = _empty_plan(action)
            return ForesightAnalysis(
                analysis_id=uuid7(),
                action=action,
                best_plan=empty,
                safest_plan=empty,
                fastest_plan=empty,
                expected_plan=empty,
                plan_spread=0.0,
                strategy_uncertainty=1.0,
                horizon_risk=0.0,
                template_version=FORESIGHT_TEMPLATE_VERSION,
                plans=[],
            )
        evaluated: list[FuturePlan] = []
        for idx, actions in enumerate(plans_list):
            confidence = _PLAN_CONFIDENCE[idx] if idx < len(_PLAN_CONFIDENCE) else 0.25
            evaluated.append(self.evaluator.evaluate(state, actions, confidence=confidence))
        selected = self.ranker.select(evaluated)
        metrics = self.ranker.metrics(evaluated)
        return ForesightAnalysis(
            analysis_id=uuid7(),
            action=action,
            best_plan=selected["best_plan"],
            safest_plan=selected["safest_plan"],
            fastest_plan=selected["fastest_plan"],
            expected_plan=selected["expected_plan"],
            plan_spread=metrics["plan_spread"],
            strategy_uncertainty=metrics["strategy_uncertainty"],
            horizon_risk=metrics["horizon_risk"],
            template_version=FORESIGHT_TEMPLATE_VERSION,
            plans=list(evaluated),
        )

    def evaluate_custom(self, state: WorldState, actions: list[str]) -> FuturePlan:
        return self.evaluator.evaluate(state, actions, confidence=0.5)
