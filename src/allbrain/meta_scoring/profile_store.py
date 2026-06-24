from __future__ import annotations

from typing import Any

from allbrain.meta_scoring.model import (
    META_SCORING_DEFAULT_WEIGHTS,
    ScoringProfile,
)


class ProfileStore:
    """Per-fault-type registry of ScoringProfiles.

    Falls back to a built-in default profile (Sprint72 weights) when no profile
    has been learned for a fault_type.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, ScoringProfile] = {}

    def get(self, fault_type: str) -> ScoringProfile:
        if fault_type in self._profiles:
            return self._profiles[fault_type]
        return self._default_for(fault_type)

    def set(self, profile: ScoringProfile) -> None:
        normalized = self._clamp(profile)
        if profile.fault_type in self._profiles:
            normalized.version = self._profiles[profile.fault_type].version + 1
        else:
            normalized.version = 1
        self._profiles[profile.fault_type] = normalized

    def all_profiles(self) -> dict[str, dict[str, Any]]:
        return {ft: p.to_dict() for ft, p in self._profiles.items()}

    def _default_for(self, fault_type: str) -> ScoringProfile:
        return ScoringProfile(
            fault_type=fault_type,
            success_weight=META_SCORING_DEFAULT_WEIGHTS["success_rate"],
            risk_weight=META_SCORING_DEFAULT_WEIGHTS["risk_penalty"],
            stability_weight=META_SCORING_DEFAULT_WEIGHTS["stability_bonus"],
            drift_weight=META_SCORING_DEFAULT_WEIGHTS["drift_penalty"],
            exploration_bonus=0.0,
            version=0,
        )

    @staticmethod
    def _clamp(profile: ScoringProfile) -> ScoringProfile:
        from allbrain.meta_scoring.model import META_SCORING_WEIGHT_MIN, META_SCORING_WEIGHT_MAX
        return ScoringProfile(
            fault_type=profile.fault_type,
            success_weight=max(META_SCORING_WEIGHT_MIN, min(META_SCORING_WEIGHT_MAX, profile.success_weight)),
            risk_weight=max(META_SCORING_WEIGHT_MIN, min(META_SCORING_WEIGHT_MAX, profile.risk_weight)),
            stability_weight=max(META_SCORING_WEIGHT_MIN, min(META_SCORING_WEIGHT_MAX, profile.stability_weight)),
            drift_weight=max(META_SCORING_WEIGHT_MIN, min(META_SCORING_WEIGHT_MAX, profile.drift_weight)),
            exploration_bonus=max(0.0, min(0.30, profile.exploration_bonus)),
            version=profile.version,
        )