from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SOFT_REPAIR_TEMPLATE_VERSION = 1

BLEND_ALPHA_MIN = 0.2
BLEND_ALPHA_MAX = 0.8

DEFAULT_BLEND_THRESHOLD = 0.70
HARD_UPDATE_THRESHOLD = 0.70


@dataclass(frozen=True)
class BlendConfig:
    old_weight: float
    new_weight: float
    stability_score: float


@dataclass(frozen=True)
class BlendedPolicy:
    old_policy_id: str
    new_policy_id: str
    fault_type: str
    old_weight: float
    new_weight: float
    blended_data: dict[str, Any] = field(default_factory=dict)
    stability_score: float = 0.0
