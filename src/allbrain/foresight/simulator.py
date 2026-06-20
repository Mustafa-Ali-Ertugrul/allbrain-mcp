from __future__ import annotations

from allbrain.world.models import Prediction, WorldState
from allbrain.world.simulation import SimulationBridge


class MultiStepSimulator:
    def __init__(self, simulator: SimulationBridge) -> None:
        self.simulator = simulator

    def simulate(self, state: WorldState, actions: list[str]) -> tuple[WorldState, list[Prediction], list[WorldState]]:
        predictions: list[Prediction] = []
        step_states: list[WorldState] = [state]
        current = state
        for action in actions:
            result = self.simulator.simulate(current, action)
            predictions.append(result.prediction)
            current = result.next_state
            step_states.append(current)
        return current, predictions, step_states
