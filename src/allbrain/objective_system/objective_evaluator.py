from __future__ import annotations

from allbrain.objective_system.model import (
    ObjectiveResult, ObjectiveWeights, ObjectivePriority,
    OBJECTIVE_PRIORITY_DEFAULTS, OBJECTIVE_REBALANCE_INTERVAL,
    OBJECTIVE_WEIGHT_MIN, OBJECTIVE_WEIGHT_MAX,
)
from allbrain.objective_system.objective_store import ObjectiveStore


class ObjectiveEvaluator:
    """Evaluates whether objectives are being met and rebalances weights.

    Rebalancing: every N cycles (25), only when oscillation is low.
    """

    def __init__(self, store: ObjectiveStore | None = None) -> None:
        self._store = store or ObjectiveStore()
        self._cycle_counter: int = 0
        self._score_history: dict[str, list[float]] = {}

    @property
    def store(self) -> ObjectiveStore:
        return self._store

    def evaluate(self, result: ObjectiveResult) -> dict[str, float]:
        key = result.fault_type
        self._score_history.setdefault(key, [])
        self._score_history[key].append(result.normalized["safety"])
        if len(self._score_history[key]) > 20:
            self._score_history[key] = self._score_history[key][-20:]
        return result.normalized

    def maybe_rebalance(self, fault_type: str, oscillation_low: bool) -> ObjectiveWeights | None:
        self._cycle_counter += 1
        if self._cycle_counter % OBJECTIVE_REBALANCE_INTERVAL != 0 or not oscillation_low:
            return None
        current = self._store.get(fault_type)
        buf = self._score_history.get(fault_type, [])
        if len(buf) < 10:
            return None
        avg_safety = sum(buf) / len(buf)
        drift = avg_safety - current.safety
        adjusted = current.safety + drift * 0.05
        adjusted = max(OBJECTIVE_WEIGHT_MIN, min(OBJECTIVE_WEIGHT_MAX, adjusted))
        if abs(adjusted - current.safety) < 0.01:
            return None
        new_weights = ObjectiveWeights(
            fault_type=fault_type, safety=round(adjusted, 4),
            stability=current.stability, success=current.success,
            efficiency=current.efficiency, version=current.version,
        )
        self._store.set(new_weights)
        return self._store.get(fault_type)

    def get_priority(self, objective_name: str) -> ObjectivePriority:
        return OBJECTIVE_PRIORITY_DEFAULTS.get(objective_name, ObjectivePriority.OPTIONAL)