from __future__ import annotations

from allbrain.meta_optimizer.gradient_estimator import GradientEstimator
from allbrain.meta_optimizer.model import (
    META_OPTIMIZER_EXPLORATION_BOUND,
    META_OPTIMIZER_UPDATE_INTERVAL,
    META_OPTIMIZER_WEIGHT_MAX,
    META_OPTIMIZER_WEIGHT_MIN,
)
from allbrain.meta_scoring.model import ScoringProfile
from allbrain.meta_scoring.profile_store import ProfileStore


class WeightOptimizer:
    """Applies gradient-like updates to ScoringProfiles.

    Guarded by:
    - stability_controller (external gate)
    - update interval (every N cycles)
    - weight clamping [MIN, MAX]
    - exploration bound [0, EXPLORATION_BOUND]
    """

    def __init__(self, profile_store: ProfileStore, gradient_estimator: GradientEstimator | None = None) -> None:
        self._store = profile_store
        self._grad = gradient_estimator or GradientEstimator()
        self._cycle_counter: dict[str, int] = {}

    @property
    def profile_store(self) -> ProfileStore:
        return self._store

    def step(
        self,
        fault_type: str,
        delta_success: float,
        delta_risk: float,
        delta_stability: float,
        delta_drift: float,
    ) -> ScoringProfile | None:
        self._cycle_counter.setdefault(fault_type, 0)
        self._cycle_counter[fault_type] += 1

        if self._cycle_counter[fault_type] % META_OPTIMIZER_UPDATE_INTERVAL != 0:
            return None

        current = self._store.get(fault_type)
        grad = self._grad.estimate(current, delta_success, delta_risk, delta_stability, delta_drift)

        updated = ScoringProfile(
            fault_type=fault_type,
            success_weight=self._clamp(current.success_weight + grad.get("success_weight", 0.0)),
            risk_weight=self._clamp(current.risk_weight + grad.get("risk_weight", 0.0)),
            stability_weight=self._clamp(current.stability_weight + grad.get("stability_weight", 0.0)),
            drift_weight=self._clamp(current.drift_weight + grad.get("drift_weight", 0.0)),
            exploration_bonus=self._clamp_exploration(
                current.exploration_bonus + grad.get("exploration_bonus", 0.0)
                if "exploration_bonus" in grad else current.exploration_bonus
            ),
            version=current.version,
        )
        self._store.set(updated)
        return self._store.get(fault_type)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(META_OPTIMIZER_WEIGHT_MIN, min(META_OPTIMIZER_WEIGHT_MAX, value))

    @staticmethod
    def _clamp_exploration(value: float) -> float:
        return max(0.0, min(META_OPTIMIZER_EXPLORATION_BOUND, value))
