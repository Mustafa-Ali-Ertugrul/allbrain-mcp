from __future__ import annotations

from allbrain.domains.learning.coevolution.model import (
    COEVOLUTION_DAMPING,
    CoEvolutionState,
    Coupling,
)


class CouplingMatrix:
    """Manages the bidirectional coupling between policy and scorer strength."""

    def __init__(self, coupling: Coupling | None = None) -> None:
        self._coupling = coupling or Coupling()

    def step(self, state: CoEvolutionState) -> CoEvolutionState:
        damped_p = state.policy_strength * (1.0 - COEVOLUTION_DAMPING) + 0.5 * COEVOLUTION_DAMPING
        damped_s = state.scorer_strength * (1.0 - COEVOLUTION_DAMPING) + 0.5 * COEVOLUTION_DAMPING

        new_p, new_s = self._coupling.apply(damped_p, damped_s)
        state.policy_strength = new_p
        state.scorer_strength = new_s
        state.cycle += 1
        state.version += 1
        return state


class Dynamics:
    """One-step simulation of the co-evolution loop.

    Alternating update: odd cycles → policy, even cycles → scorer.
    Updates are damped by COEVOLUTION_DAMPING.
    """

    def __init__(self, coupling_matrix: CouplingMatrix | None = None) -> None:
        self._coupling = coupling_matrix or CouplingMatrix()

    def step(self, state: CoEvolutionState, policy_update: bool) -> CoEvolutionState:
        updated = self._coupling.step(state)
        if policy_update:
            updated.policy_strength += (1.0 - updated.policy_strength) * COEVOLUTION_DAMPING
        else:
            updated.scorer_strength += (1.0 - updated.scorer_strength) * COEVOLUTION_DAMPING
        return updated
