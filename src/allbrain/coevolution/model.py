from __future__ import annotations

from dataclasses import dataclass, field

COEVOLUTION_TEMPLATE_VERSION = 1

COEVOLUTION_DAMPING = 0.30
COEVOLUTION_OSCILLATION_THRESHOLD = 0.30
COEVOLUTION_WINDOW_SIZE = 15
COEVOLUTION_MIN_STRENGTH = 0.05
COEVOLUTION_MAX_STRENGTH = 0.95


@dataclass
class Coupling:
    """2x2 coupling matrix between policy and scorer.

    M = [[p2p, p2s],
         [s2p, s2s]]
    """
    p2p: float = 0.85
    p2s: float = 0.15
    s2p: float = 0.10
    s2s: float = 0.90

    def apply(self, policy_strength: float, scorer_strength: float) -> tuple[float, float]:
        new_p = self.p2p * policy_strength + self.p2s * scorer_strength
        new_s = self.s2p * policy_strength + self.s2s * scorer_strength
        return (min(COEVOLUTION_MAX_STRENGTH, max(COEVOLUTION_MIN_STRENGTH, new_p)),
                min(COEVOLUTION_MAX_STRENGTH, max(COEVOLUTION_MIN_STRENGTH, new_s)))


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
