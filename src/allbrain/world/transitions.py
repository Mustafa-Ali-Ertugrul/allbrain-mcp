from __future__ import annotations

from allbrain.world.models import WorldState


_ACTION_ENV: dict[str, dict[str, str]] = {
    "deploy": {"deployment": "running"},
    "run_tests": {"tests": "passed"},
    "rollback": {"deployment": "rolled_back"},
    "scale": {"deployment": "scaled"},
}


class StateTransitionBridge:
    def predict(self, state: WorldState, action: str) -> WorldState:
        env_updates = _ACTION_ENV.get(action, {})
        if not env_updates:
            return state
        merged = {**state.environment_state, **env_updates}
        return state.model_copy(update={"environment_state": merged})
