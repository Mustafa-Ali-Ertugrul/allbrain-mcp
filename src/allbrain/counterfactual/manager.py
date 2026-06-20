from __future__ import annotations

from allbrain.counterfactual.evaluator import CounterfactualEvaluator
from allbrain.counterfactual.generator import AlternativeGenerator
from allbrain.counterfactual.models import CounterfactualResult
from allbrain.counterfactual.ranking import AlternativeRanker
from allbrain.world import PredictionBridge, SimulationBridge, StateTransitionBridge


def _default_simulator() -> SimulationBridge:
    return SimulationBridge(StateTransitionBridge(), PredictionBridge())


class CounterfactualEngine:
    def __init__(
        self,
        generator: AlternativeGenerator | None = None,
        evaluator: CounterfactualEvaluator | None = None,
        ranker: AlternativeRanker | None = None,
    ) -> None:
        self.generator = generator or AlternativeGenerator()
        self.evaluator = evaluator or CounterfactualEvaluator(_default_simulator())
        self.ranker = ranker or AlternativeRanker()

    def analyze(self, state, action: str, *, limit: int | None = None) -> list[CounterfactualResult]:
        alternatives = self.generator.generate(action)
        if limit is not None and limit >= 0:
            alternatives = alternatives[:limit]
        results: list[CounterfactualResult] = []
        for alternative in alternatives:
            results.append(self.evaluator.compare(state, action, alternative))
        return results

    def rank(self, state, actions: list[str]) -> list:
        return self.ranker.rank(state, actions)
