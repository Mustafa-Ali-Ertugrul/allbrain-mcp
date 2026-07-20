from __future__ import annotations

from allbrain.domains.reasoning.counterfactual.models import RankedAlternative
from allbrain.world import PredictionBridge, SimulationBridge, StateTransitionBridge


class AlternativeRanker:
    def rank(self, state, actions: list[str], simulator: SimulationBridge | None = None) -> list[RankedAlternative]:
        if simulator is None:
            simulator = SimulationBridge(StateTransitionBridge(), PredictionBridge())
        results: list[RankedAlternative] = []
        for action in actions:
            simulation = simulator.simulate(state, action)
            score = round(simulation.prediction.success_probability - simulation.prediction.risk, 6)
            results.append(
                RankedAlternative(
                    action=action,
                    score=score,
                    prediction=simulation.prediction,
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)
