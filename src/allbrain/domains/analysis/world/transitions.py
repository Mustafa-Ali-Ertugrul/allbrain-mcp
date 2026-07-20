from __future__ import annotations

import random as _random

from allbrain.domains.analysis.world.models import WorldState
from allbrain.domains.analysis.world.transition_learner import TransitionLearner

_ACTION_ENV: dict[str, dict[str, str]] = {
    "deploy": {"deployment": "running"},
    "run_tests": {"tests": "passed"},
    "rollback": {"deployment": "rolled_back"},
    "scale": {"deployment": "scaled"},
}


class StateTransitionBridge:
    """Hardcoded deterministic transition engine (legacy / cold-start fallback)."""

    def predict(self, state: WorldState, action: str) -> WorldState:
        env_updates = _ACTION_ENV.get(action, {})
        if not env_updates:
            return state
        merged = {**state.environment_state, **env_updates}
        return state.model_copy(update={"environment_state": merged})


class LearnedTransitionBridge:
    """Stochastic transition engine that learns from the event log.

    Uses a TransitionLearner's frequency table to sample next-states via
    Monte Carlo.  Falls back to the hardcoded StateTransitionBridge when
    insufficient data exists or when the action is unknown and no similar
    action can be found.
    """

    def __init__(
        self,
        learner: TransitionLearner,
        fallback: StateTransitionBridge | None = None,
    ) -> None:
        self._learner = learner
        self._fallback = fallback or StateTransitionBridge()

    def predict(self, state: WorldState, action: str) -> WorldState:
        # 1. Try exact action match
        dist = self._learner.predict_distribution(state, action)

        # 2. If no data, try the most similar known action
        if not dist:
            similar = self._learner.find_similar_action(action)
            if similar is not None:
                dist = self._learner.predict_distribution(state, similar)

        # 3. If still no data, fall back to hardcoded bridge
        if not dist:
            return self._fallback.predict(state, action)

        # 4. Monte Carlo sampling
        env_states, probs = zip(*dist, strict=False)
        chosen_env: dict[str, str] = _random.choices(env_states, weights=probs, k=1)[0]

        # 5. Merge chosen environment into current state (same semantics as
        #    StateTransitionBridge: action wins on conflict)
        merged = {**state.environment_state, **chosen_env}
        return state.model_copy(update={"environment_state": merged})
