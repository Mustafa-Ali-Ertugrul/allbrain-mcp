from __future__ import annotations

from typing import Any

from allbrain.meta_meta_scoring.model import EvaluatorProfile


class EvaluatorStore:
    """Per-evaluator per-fault-type registry of EvaluatorProfiles."""

    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, EvaluatorProfile]] = {}

    def get(self, evaluator_id: str, fault_type: str) -> EvaluatorProfile:
        sub = self._profiles.setdefault(evaluator_id, {})
        if fault_type in sub:
            return sub[fault_type]
        return EvaluatorProfile(evaluator_id=evaluator_id, fault_type=fault_type, version=0)

    def set(self, profile: EvaluatorProfile) -> None:
        sub = self._profiles.setdefault(profile.evaluator_id, {})
        existing = sub.get(profile.fault_type)
        if existing is not None:
            profile.version = existing.version + 1
        else:
            profile.version = 1
        sub[profile.fault_type] = self._clamp(profile)

    def all_profiles(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {
            eid: {ft: p.to_dict() for ft, p in m.items()}
            for eid, m in self._profiles.items()
        }

    @staticmethod
    def _clamp(profile: EvaluatorProfile) -> EvaluatorProfile:
        return EvaluatorProfile(
            evaluator_id=profile.evaluator_id,
            fault_type=profile.fault_type,
            accuracy=max(0.0, min(1.0, profile.accuracy)),
            bias=max(-1.0, min(1.0, profile.bias)),
            stability=max(0.0, min(1.0, profile.stability)),
            drift_sensitivity=max(0.0, min(1.0, profile.drift_sensitivity)),
            version=profile.version,
        )