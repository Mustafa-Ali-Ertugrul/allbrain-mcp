from __future__ import annotations

from allbrain.objective_system.model import (
    FAULT_TYPE_WEIGHTS,
    OBJECTIVE_DEFAULTS_GLOBAL,
    ObjectiveWeights,
)


class ObjectiveStore:
    """Per-fault-type registry of ObjectiveWeights with global fallback."""

    def __init__(self) -> None:
        self._weights: dict[str, ObjectiveWeights] = {}

    def get(self, fault_type: str) -> ObjectiveWeights:
        if fault_type in self._weights:
            return self._weights[fault_type]
        if fault_type in FAULT_TYPE_WEIGHTS:
            return ObjectiveWeights(fault_type=fault_type, **FAULT_TYPE_WEIGHTS[fault_type], version=0)
        return ObjectiveWeights(fault_type=fault_type, **OBJECTIVE_DEFAULTS_GLOBAL, version=0)

    def set(self, weights: ObjectiveWeights) -> None:
        normalized = self._normalize(weights)
        existing = self._weights.get(weights.fault_type)
        normalized.version = (existing.version + 1) if existing else 1
        self._weights[weights.fault_type] = normalized

    def all_weights(self) -> dict[str, dict[str, float]]:
        return {ft: w.to_dict() for ft, w in self._weights.items()}

    @staticmethod
    def _normalize(weights: ObjectiveWeights) -> ObjectiveWeights:
        from allbrain.objective_system.model import OBJECTIVE_WEIGHT_MAX, OBJECTIVE_WEIGHT_MIN
        s = max(OBJECTIVE_WEIGHT_MIN, min(OBJECTIVE_WEIGHT_MAX, weights.safety))
        st = max(OBJECTIVE_WEIGHT_MIN, min(OBJECTIVE_WEIGHT_MAX, weights.stability))
        su = max(OBJECTIVE_WEIGHT_MIN, min(OBJECTIVE_WEIGHT_MAX, weights.success))
        e = max(OBJECTIVE_WEIGHT_MIN, min(OBJECTIVE_WEIGHT_MAX, weights.efficiency))
        total = s + st + su + e
        if total > 1.0:
            s /= total; st /= total; su /= total; e /= total
        return ObjectiveWeights(fault_type=weights.fault_type, safety=round(s,4),
            stability=round(st,4), success=round(su,4), efficiency=round(e,4),
            version=weights.version)
