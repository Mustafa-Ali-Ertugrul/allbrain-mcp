from __future__ import annotations

from typing import Callable

from allbrain.learning_safety.model import MAX_SIMULATION_WEIGHT


RealProvider = Callable[[str, float, float], tuple[float, bool, float]]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class OutcomeValidator:
    """Validates and weights outcome measurements.

    Combines simulated and real provider outputs with configurable
    weights, enforcing MAX_SIMULATION_WEIGHT cap to prevent
    simulation bias dominating learning.
    """

    def __init__(
        self,
        real_provider: RealProvider | None = None,
        simulation_weight: float = MAX_SIMULATION_WEIGHT,
    ) -> None:
        self._real = real_provider
        self._sim_weight = _clamp(simulation_weight, 0.0, MAX_SIMULATION_WEIGHT)
        self._was_capped = False

    def set_real_provider(self, provider: RealProvider | None) -> None:
        self._real = provider
        self._was_capped = False

    def call_real_provider(
        self, strategy: str, pre_risk: float, urgency: float,
    ) -> tuple[float, bool, float] | None:
        """Invoke the real provider if set. Returns None if not configured."""
        if self._real is None:
            return None
        return self._real(strategy, pre_risk, urgency)

    @property
    def simulation_weight(self) -> float:
        return self._sim_weight

    @property
    def real_weight(self) -> float:
        return 1.0 - self._sim_weight

    def is_real_provider_set(self) -> bool:
        return self._real is not None

    def was_capped(self) -> bool:
        return self._was_capped

    def compute_combined_effectiveness(
        self,
        sim_effectiveness: float,
        real_effectiveness: float | None,
    ) -> tuple[float, bool]:
        """Compute combined effectiveness score.

        Returns (combined_value, was_capped).
        When real provider is missing, returns sim effectiveness
        and flags was_capped=True.
        """
        if self._real is None or real_effectiveness is None:
            self._was_capped = True
            return sim_effectiveness, True
        combined = (
            self._sim_weight * sim_effectiveness
            + self.real_weight * real_effectiveness
        )
        return _clamp(combined, -1.0, 1.0), False

    def compute_combined_risk_delta(
        self,
        sim_risk_delta: float,
        real_risk_delta: float | None,
    ) -> tuple[float, bool]:
        """Compute combined risk_delta.

        Returns (combined_delta, was_capped).
        """
        if self._real is None or real_risk_delta is None:
            self._was_capped = True
            return sim_risk_delta, True
        combined = (
            self._sim_weight * sim_risk_delta
            + self.real_weight * real_risk_delta
        )
        return _clamp(combined, -1.0, 1.0), False
