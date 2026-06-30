from __future__ import annotations

import math
from collections.abc import Iterable

from allbrain.learning_safety.model import (
    DEFAULT_BASE_EPSILON,
    DEFAULT_DECAY_RATE,
    EntropyState,
)


def shannon_entropy(probabilities: Iterable[float]) -> float:
    """Compute Shannon entropy H = -Σ p_i * log(p_i).

    Returns 0.0 if all probabilities are zero or empty.
    """
    ps = [p for p in probabilities if p > 0]
    if not ps:
        return 0.0
    return -sum(p * math.log(p) for p in ps)


def entropy_decay(initial_eps: float, decay: float, n_cycles: int) -> float:
    """Compute decayed epsilon: eps_t = initial_eps * decay^t."""
    return initial_eps * (decay**n_cycles)


class EntropyCalculator:
    """Tracks epsilon decay across cycles and computes entropy from stats."""

    def __init__(
        self,
        base_epsilon: float = DEFAULT_BASE_EPSILON,
        decay_rate: float = DEFAULT_DECAY_RATE,
    ) -> None:
        self._base_eps = base_epsilon
        self._decay = decay_rate
        self._cycle_count = 0

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def base_epsilon(self) -> float:
        return self._base_eps

    @property
    def decay_rate(self) -> float:
        return self._decay

    def current_epsilon(self) -> float:
        return entropy_decay(self._base_eps, self._decay, self._cycle_count)

    def advance(self) -> None:
        self._cycle_count += 1

    def reset(self) -> None:
        self._cycle_count = 0

    @staticmethod
    def from_strategy_counts(counts: dict[str, int]) -> EntropyState:
        total = sum(counts.values())
        if total == 0:
            return EntropyState(
                entropy=0.0,
                n_strategies=0,
                epsilon_current=0.0,
                cycle_count=0,
            )
        probs = [c / total for c in counts.values()]
        H = shannon_entropy(probs)
        return EntropyState(
            entropy=H,
            n_strategies=len(counts),
            epsilon_current=0.0,
            cycle_count=0,
        )
