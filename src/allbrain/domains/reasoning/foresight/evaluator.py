from __future__ import annotations

from allbrain.domains.analysis.world.models import WorldState
from allbrain.domains.reasoning.foresight.models import FuturePlan
from allbrain.domains.reasoning.foresight.simulator import MultiStepSimulator


class PlanEvaluator:
    def __init__(self, simulator: MultiStepSimulator, *, max_horizon: int, confidence_decay: float = 0.90) -> None:
        self.simulator = simulator
        self.max_horizon = max_horizon
        self.confidence_decay = confidence_decay

    def evaluate(self, state: WorldState, actions: list[str], *, confidence: float) -> FuturePlan:
        if len(actions) > self.max_horizon:
            raise ValueError(f"plan horizon {len(actions)} exceeds max_horizon {self.max_horizon}")
        final_state, predictions, step_states = self.simulator.simulate(state, actions)
        predicted_success = predictions[-1].success_probability if predictions else 0.0
        if predictions:
            # Geometric decay weights: w_i = decay^(i+1) (1-indexed)
            weights = [self.confidence_decay ** (i + 1) for i in range(len(predictions))]
            total_weight = sum(weights)
            cumulative_risk = round(
                sum(w * p.risk for w, p in zip(weights, predictions, strict=True)) / total_weight, 6
            )
            cumulative_cost = round(
                sum(w * p.cost for w, p in zip(weights, predictions, strict=True)) / total_weight, 6
            )
        else:
            cumulative_risk = 0.0
            cumulative_cost = 0.0
        return FuturePlan(
            actions=list(actions),
            predicted_success=round(predicted_success, 6),
            cumulative_risk=cumulative_risk,
            cumulative_cost=cumulative_cost,
            horizon=len(actions),
            confidence=confidence,
            step_states=step_states,
        )
