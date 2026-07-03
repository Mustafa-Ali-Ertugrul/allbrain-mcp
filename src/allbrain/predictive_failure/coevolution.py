from __future__ import annotations

from dataclasses import dataclass

COEVOLUTION_TEMPLATE_VERSION = 1

COEVOLUTION_DAMPING = 0.30
COEVOLUTION_OSCILLATION_THRESHOLD = 0.30
COEVOLUTION_WINDOW_SIZE = 15
COEVOLUTION_MIN_STRENGTH = 0.05
COEVOLUTION_MAX_STRENGTH = 0.95


@dataclass
class Coupling:
    p2p: float = 0.85
    p2s: float = 0.15
    s2p: float = 0.10
    s2s: float = 0.90

    def apply(self, policy_strength: float, scorer_strength: float) -> tuple[float, float]:
        new_p = self.p2p * policy_strength + self.p2s * scorer_strength
        new_s = self.s2p * policy_strength + self.s2s * scorer_strength
        return (
            min(COEVOLUTION_MAX_STRENGTH, max(COEVOLUTION_MIN_STRENGTH, new_p)),
            min(COEVOLUTION_MAX_STRENGTH, max(COEVOLUTION_MIN_STRENGTH, new_s)),
        )


@dataclass
class CoEvolutionState:
    policy_strength: float = 0.75
    scorer_strength: float = 0.75
    oscillation_index: float = 0.0
    cycle: int = 0
    version: int = 1

    def to_dict(self) -> dict[str, float]:
        return {
            "policy_strength": round(self.policy_strength, 4),
            "scorer_strength": round(self.scorer_strength, 4),
            "oscillation_index": round(self.oscillation_index, 4),
        }


class CouplingMatrix:
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
    def __init__(self, coupling_matrix: CouplingMatrix | None = None) -> None:
        self._coupling = coupling_matrix or CouplingMatrix()

    def step(self, state: CoEvolutionState, policy_update: bool) -> CoEvolutionState:
        updated = self._coupling.step(state)
        if policy_update:
            updated.policy_strength += (1.0 - updated.policy_strength) * COEVOLUTION_DAMPING
        else:
            updated.scorer_strength += (1.0 - updated.scorer_strength) * COEVOLUTION_DAMPING
        return updated


class OscillationDetector:
    def __init__(self) -> None:
        self._deltas: dict[str, list[float]] = {}

    def record(self, fault_type: str, delta: float) -> None:
        self._deltas.setdefault(fault_type, [])
        buf = self._deltas[fault_type]
        buf.append(delta)
        if len(buf) > COEVOLUTION_WINDOW_SIZE:
            buf.pop(0)

    def is_oscillating(self, fault_type: str) -> bool:
        buf = self._deltas.get(fault_type, [])
        if len(buf) < 4:
            return False
        mean = sum(buf) / len(buf)
        variance = sum((d - mean) ** 2 for d in buf) / len(buf)
        return (variance**0.5) > COEVOLUTION_OSCILLATION_THRESHOLD

    def oscillation_index(self, fault_type: str) -> float:
        buf = self._deltas.get(fault_type, [])
        if len(buf) < 4:
            return 0.0
        mean = sum(buf) / len(buf)
        variance = sum((d - mean) ** 2 for d in buf) / len(buf)
        return min(1.0, (variance**0.5) / COEVOLUTION_OSCILLATION_THRESHOLD)

    def clear(self) -> None:
        self._deltas.clear()
