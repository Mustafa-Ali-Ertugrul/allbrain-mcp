from __future__ import annotations

from allbrain.world.models import Prediction, WorldState
from allbrain.world.simulation import SimulationBridge


class MultiStepSimulator:
    MIN_CONFIDENCE = 0.35

    def __init__(self, simulator: SimulationBridge, *, confidence_decay: float = 0.90) -> None:
        self.simulator = simulator
        self.confidence_decay = confidence_decay

    def simulate(self, state: WorldState, actions: list[str]) -> tuple[WorldState, list[Prediction], list[WorldState]]:
        predictions: list[Prediction] = []
        step_states: list[WorldState] = [state]
        current = state
        for step_idx, action in enumerate(actions):
            result = self.simulator.simulate(current, action)
            step_num = step_idx + 1  # 1-indexed
            multiplier = self.confidence_decay**step_num
            effective_confidence = result.prediction.confidence * multiplier
            if effective_confidence < self.MIN_CONFIDENCE:
                break
            decayed_prediction = result.prediction.model_copy(update={"confidence": effective_confidence})
            predictions.append(decayed_prediction)
            current = result.next_state
            step_states.append(current)
        return current, predictions, step_states
