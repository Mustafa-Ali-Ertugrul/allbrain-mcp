from __future__ import annotations

from allbrain.domains.analysis.world.models import WorldState
from allbrain.domains.analysis.world.simulation import SimulationBridge

ACTION_MAP: dict[str, list[str]] = {
    "deploy": ["run_tests", "delay_deploy", "rollback"],
    "delete": ["backup", "archive"],
}


class AlternativeGenerator:
    def __init__(self, simulator: SimulationBridge | None = None) -> None:
        self._simulator = simulator

    def generate(self, action: str) -> list[str]:
        return list(ACTION_MAP.get(action, []))

    def generate_with_pruning(
        self,
        action: str,
        state: WorldState | None = None,
        *,
        risk_threshold: float = 1.0,
        confidence_threshold: float = 0.0,
        cost_threshold: float = 1.0,
    ) -> list[str]:
        """Generate alternatives and prune those exceeding risk/confidence/cost thresholds.

        When *state* and a simulator are available, each alternative is simulated
        and pruned if any threshold is exceeded.  Without a simulator the raw
        list is returned unchanged.
        """
        raw = self.generate(action)
        if self._simulator is None or state is None:
            return raw

        pruned: list[str] = []
        for alt in raw:
            sim = self._simulator.simulate(state, alt)
            pred = sim.prediction
            if pred.risk <= risk_threshold and pred.confidence >= confidence_threshold and pred.cost <= cost_threshold:
                pruned.append(alt)
        return pruned
