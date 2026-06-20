from __future__ import annotations

from allbrain.foresight.models import FuturePlan
from allbrain.foresight.simulator import MultiStepSimulator
from allbrain.world.models import WorldState


class PlanEvaluator:
    def __init__(self, simulator: MultiStepSimulator, *, max_horizon: int) -> None:
        self.simulator = simulator
        self.max_horizon = max_horizon

    def evaluate(self, state: WorldState, actions: list[str], *, confidence: float) -> FuturePlan:
        if len(actions) > self.max_horizon:
            raise ValueError(f"plan horizon {len(actions)} exceeds max_horizon {self.max_horizon}")
        final_state, predictions, step_states = self.simulator.simulate(state, actions)
        predicted_success = predictions[-1].success_probability if predictions else 0.0
        cumulative_risk = round(sum(p.risk for p in predictions) / len(predictions), 6) if predictions else 0.0
        cumulative_cost = round(sum(p.cost for p in predictions) / len(predictions), 6) if predictions else 0.0
        return FuturePlan(
            actions=list(actions),
            predicted_success=round(predicted_success, 6),
            cumulative_risk=cumulative_risk,
            cumulative_cost=cumulative_cost,
            horizon=len(actions),
            confidence=confidence,
            step_states=step_states,
        )
