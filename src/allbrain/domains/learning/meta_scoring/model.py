from __future__ import annotations

from dataclasses import dataclass
from typing import Any

META_SCORING_TEMPLATE_VERSION = 1

META_SCORING_DEFAULT_WEIGHTS: dict[str, float] = {
    "success_rate": 0.50,
    "risk_penalty": 0.20,
    "stability_bonus": 0.20,
    "drift_penalty": 0.10,
}

META_SCORING_WEIGHT_MIN = 0.05
META_SCORING_WEIGHT_MAX = 0.70
META_SCORING_OVERRIDE_CONFIDENCE = 0.15


@dataclass
class ScoringProfile:
    fault_type: str
    success_weight: float = 0.50
    risk_weight: float = 0.20
    stability_weight: float = 0.20
    drift_weight: float = 0.10
    exploration_bonus: float = 0.0
    version: int = 1

    def to_dict(self) -> dict[str, float]:
        return {
            "success_weight": self.success_weight,
            "risk_weight": self.risk_weight,
            "stability_weight": self.stability_weight,
            "drift_weight": self.drift_weight,
            "exploration_bonus": self.exploration_bonus,
        }

    @classmethod
    def from_dict(cls, fault_type: str, d: dict[str, Any]) -> ScoringProfile:
        return cls(
            fault_type=fault_type,
            success_weight=float(d.get("success_weight", 0.50)),
            risk_weight=float(d.get("risk_weight", 0.20)),
            stability_weight=float(d.get("stability_weight", 0.20)),
            drift_weight=float(d.get("drift_weight", 0.10)),
            exploration_bonus=float(d.get("exploration_bonus", 0.0)),
            version=int(d.get("version", 1)),
        )


@dataclass
class MetaScoreResult:
    static_score: float
    meta_score: float
    blended_score: float
    confidence: float
    override_applied: bool
