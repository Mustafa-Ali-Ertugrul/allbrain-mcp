from __future__ import annotations

from typing import Any

from allbrain.meta_scoring.model import (
    META_SCORING_OVERRIDE_CONFIDENCE,
    MetaScoreResult,
)
from allbrain.meta_scoring.profile_store import ProfileStore


class MetaScorer:
    """Augments the static PolicyScorer with learnable per-fault-type profiles.

    final_score = blend(static_score, meta_score, confidence)
    Override applied only when confidence >= META_SCORING_OVERRIDE_CONFIDENCE.
    """

    def __init__(self, profile_store: ProfileStore | None = None) -> None:
        self._store = profile_store or ProfileStore()

    @property
    def profile_store(self) -> ProfileStore:
        return self._store

    def score(
        self,
        fault_type: str,
        static_score: float,
        *,
        success_rate: float,
        risk_estimate: float,
        stability_estimate: float,
        drift_estimate: float,
    ) -> MetaScoreResult:
        profile = self._store.get(fault_type)

        risk_penalty = 1.0 - risk_estimate
        stability_bonus = stability_estimate
        drift_penalty = drift_estimate

        meta_score = (
            +success_rate * profile.success_weight
            - risk_penalty * profile.risk_weight
            + stability_bonus * profile.stability_weight
            - drift_penalty * profile.drift_weight
            + profile.exploration_bonus
        )

        gap = abs(meta_score - static_score)
        override = gap >= META_SCORING_OVERRIDE_CONFIDENCE

        if override:
            confidence = min(1.0, gap)
            blended = meta_score
        else:
            confidence = gap / META_SCORING_OVERRIDE_CONFIDENCE if META_SCORING_OVERRIDE_CONFIDENCE > 0 else 0.0
            blended = static_score * (1.0 - confidence) + meta_score * confidence

        return MetaScoreResult(
            static_score=static_score,
            meta_score=meta_score,
            blended_score=blended,
            confidence=confidence,
            override_applied=override,
        )

    def to_event_payload(self, result: MetaScoreResult, fault_type: str) -> dict[str, Any]:
        return {
            "fault_type": fault_type,
            "static_score": result.static_score,
            "meta_score": result.meta_score,
            "blended_score": result.blended_score,
            "confidence": result.confidence,
            "override_applied": result.override_applied,
        }
