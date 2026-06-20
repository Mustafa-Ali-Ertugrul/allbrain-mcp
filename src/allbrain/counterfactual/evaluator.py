from __future__ import annotations

from allbrain.counterfactual.models import CounterfactualResult
from allbrain.world.simulation import SimulationBridge


class CounterfactualEvaluator:
    def __init__(self, simulator: SimulationBridge) -> None:
        self.simulator = simulator

    def compare(self, state, actual_action: str, alternative_action: str) -> CounterfactualResult:
        actual = self.simulator.simulate(state, actual_action)
        alternative = self.simulator.simulate(state, alternative_action)
        improvement = round(alternative.prediction.success_probability - actual.prediction.success_probability, 6)
        regret = round(max(0.0, improvement), 6)
        recommendation = alternative_action if improvement > 0 else actual_action
        return CounterfactualResult(
            actual_action=actual_action,
            alternative_action=alternative_action,
            actual_prediction=actual.prediction,
            alternative_prediction=alternative.prediction,
            improvement=improvement,
            regret=regret,
            recommendation=recommendation,
        )
