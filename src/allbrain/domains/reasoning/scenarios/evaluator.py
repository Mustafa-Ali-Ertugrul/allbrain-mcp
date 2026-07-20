from __future__ import annotations

from allbrain.domains.reasoning.scenarios.generator import ScenarioTemplate
from allbrain.domains.reasoning.scenarios.models import ScenarioResult
from allbrain.world import WorldState
from allbrain.world.simulation import SimulationBridge


def apply_overlay(state: WorldState, template: ScenarioTemplate) -> WorldState:
    new_env = dict(state.environment_state)
    new_env.update(template.environment_state_overlay)
    for key in template.environment_state_remove:
        new_env.pop(key, None)
    new_res = dict(state.resources)
    new_res.update(template.resources_overlay)
    for key in template.resources_remove:
        new_res.pop(key, None)
    return state.model_copy(update={"environment_state": new_env, "resources": new_res})


class ScenarioEvaluator:
    def __init__(self, simulator: SimulationBridge) -> None:
        self.simulator = simulator

    def evaluate(self, state: WorldState, action: str, template: ScenarioTemplate) -> ScenarioResult:
        modified_state = apply_overlay(state, template)
        simulation = self.simulator.simulate(modified_state, action)
        return ScenarioResult(
            scenario=template.name,
            prediction=simulation.prediction,
            confidence=template.confidence,
        )
