from __future__ import annotations

from uuid6 import uuid7

from allbrain.domains.analysis.world.models import SimulationResult
from allbrain.domains.analysis.world.prediction import PredictionBridge
from allbrain.domains.analysis.world.transitions import StateTransitionBridge


class SimulationBridge:
    def __init__(
        self,
        transition_engine: StateTransitionBridge,
        prediction_engine: PredictionBridge,
    ) -> None:
        self.transitions = transition_engine
        self.predictions = prediction_engine

    def simulate(self, state, action: str) -> SimulationResult:
        next_state = self.transitions.predict(state, action)
        prediction = self.predictions.evaluate(next_state, action)
        return SimulationResult(
            simulation_id=uuid7(),
            next_state=next_state,
            prediction=prediction,
        )
