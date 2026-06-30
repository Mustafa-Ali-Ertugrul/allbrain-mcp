from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.models.schemas import EventRead
from allbrain.world.environment import EnvironmentTracker
from allbrain.world.models import SimulationResult, WorldState
from allbrain.world.prediction import PredictionBridge
from allbrain.world.prediction_learner import BetaPredictor, LearnedPredictionBridge
from allbrain.world.simulation import SimulationBridge
from allbrain.world.transition_learner import TransitionLearner
from allbrain.world.transitions import LearnedTransitionBridge, StateTransitionBridge


class WorldStateBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        observations: list[dict[str, Any]] = []
        simulations: list[dict[str, Any]] = []
        for event in canonical_event_sort(events):
            if event.type == EventType.WORLD_STATE_OBSERVED.value:
                observations.append(event.payload)
            elif event.type == EventType.WORLD_SIMULATION_RUN.value:
                simulations.append(event.payload)
        latest = observations[-1] if observations else None
        return {
            "observations": observations,
            "simulations": simulations,
            "latest_state": latest,
            "observation_count": len(observations),
            "simulation_count": len(simulations),
        }


class WorldModel:
    def __init__(
        self,
        tracker: EnvironmentTracker | None = None,
        transition_engine: StateTransitionBridge | None = None,
        prediction_engine: PredictionBridge | None = None,
    ) -> None:
        self.tracker = tracker or EnvironmentTracker()
        self._base_transitions = transition_engine or StateTransitionBridge()
        self._base_predictions = prediction_engine or PredictionBridge()
        self._learner: TransitionLearner | None = None
        self._predictor: BetaPredictor | None = None
        self.simulator = SimulationBridge(self._base_transitions, self._base_predictions)

    def learn(self, events: list) -> None:
        """Learn transition and prediction patterns from the event log.

        Builds a TransitionLearner and BetaPredictor from the given events,
        then swaps in LearnedTransitionBridge and LearnedPredictionBridge
        (with the hardcoded bridges as fallback).

        Calling ``learn`` with an empty or short event list is safe —
        the learned bridges fall back to the hardcoded bridges when
        insufficient data exists.
        """
        self._learner = TransitionLearner()
        self._learner.learn(events)
        self._predictor = BetaPredictor()
        self._predictor.learn_from_events(events)
        learned_t = LearnedTransitionBridge(self._learner, fallback=self._base_transitions)
        learned_p = LearnedPredictionBridge(self._predictor, fallback=self._base_predictions)
        self.simulator = SimulationBridge(learned_t, learned_p)

    def observe(self) -> WorldState:
        return self.tracker.capture()

    def simulate(self, action: str, current_state: WorldState) -> SimulationResult:
        return self.simulator.simulate(current_state, action)
