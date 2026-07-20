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

    @classmethod
    def from_events(cls, events: list) -> "WorldModel":
        """Rebuild WorldModel state from event history.

        Scans events for ``world_model_updated`` payloads to restore
        previously persisted transition and prediction state.  When no
        persisted state exists, returns a cold-start WorldModel with
        hardcoded bridges.

        This is the API surface for v0.4.0.  Pipeline integration
        (warm-starting the decision pipeline) ships in v0.4.1.
        """
        model = cls()
        for event in events:
            event_type = str(getattr(event, "type", ""))
            if event_type == "world_model_updated":
                payload = getattr(event, "payload", None)
                if isinstance(payload, dict):
                    model._restore_from_payload(payload)
        return model

    def _restore_from_payload(self, payload: dict) -> None:
        """Restore learner/predictor state from a serialized payload."""
        learner_data = payload.get("transitions")
        if isinstance(learner_data, dict):
            self._learner = TransitionLearner()
            raw_transitions = learner_data.get("transitions", {})
            self._learner._transitions = {}
            for key_str, next_counts in raw_transitions.items():
                parts = key_str.split("||", 1)
                if len(parts) == 2:
                    self._learner._transitions[(parts[0], parts[1])] = dict(next_counts)
            self._learner._action_counts = dict(learner_data.get("action_counts", {}))
            self._learner._state_samples = dict(learner_data.get("state_samples", {}))
            self._learner._next_state_samples = dict(learner_data.get("next_state_samples", {}))
            self._learner._known_actions = set(learner_data.get("known_actions", []))
            learned_t = LearnedTransitionBridge(self._learner, fallback=self._base_transitions)
        else:
            learned_t = self._base_transitions

        predictor_data = payload.get("predictors")
        if isinstance(predictor_data, dict):
            self._predictor = BetaPredictor()
            for action, params in predictor_data.items():
                if isinstance(params, dict):
                    self._predictor._alphas[action] = params.get("alpha", 1.0)
                    self._predictor._betas[action] = params.get("beta", 1.0)
            learned_p = LearnedPredictionBridge(self._predictor, fallback=self._base_predictions)
        else:
            learned_p = self._base_predictions

        self.simulator = SimulationBridge(learned_t, learned_p)

    def serialize_transitions(self) -> dict:
        """Serialize learned transitions for event-store persistence.

        Returns a JSON-serializable dict of transition probabilities
        and beta parameters, suitable for ``append_event()`` payload.
        Returns an empty dict when no learning has occurred.
        """
        result: dict = {"version": 1}

        if self._learner is not None:
            result["transitions"] = {
                "transitions": {
                    f"{k[0]}||{k[1]}": dict(v)
                    for k, v in self._learner._transitions.items()
                },
                "action_counts": dict(self._learner._action_counts),
                "state_samples": dict(self._learner._state_samples),
                "next_state_samples": dict(self._learner._next_state_samples),
                "known_actions": sorted(self._learner._known_actions),
            }

        if self._predictor is not None:
            result["predictors"] = {
                action: {"alpha": self._predictor._alphas.get(action, 1.0), "beta": self._predictor._betas.get(action, 1.0)}
                for action in self._predictor._alphas
            }

        return result

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
