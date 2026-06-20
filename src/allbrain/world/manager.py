from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.world.environment import EnvironmentTracker
from allbrain.world.models import SimulationResult, WorldState
from allbrain.world.prediction import PredictionBridge
from allbrain.world.simulation import SimulationBridge
from allbrain.world.transitions import StateTransitionBridge


class WorldStateBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        observations: list[dict[str, Any]] = []
        simulations: list[dict[str, Any]] = []
        for event in sorted(events, key=lambda item: (item.created_at, item.id)):
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
        self.transitions = transition_engine or StateTransitionBridge()
        self.predictions = prediction_engine or PredictionBridge()
        self.simulator = SimulationBridge(self.transitions, self.predictions)

    def observe(self) -> WorldState:
        return self.tracker.capture()

    def simulate(self, action: str, current_state: WorldState) -> SimulationResult:
        return self.simulator.simulate(current_state, action)
