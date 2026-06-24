from __future__ import annotations

from typing import Any

from allbrain.soft_repair.model import (
    BlendedPolicy,
    BlendConfig,
    DEFAULT_BLEND_THRESHOLD,
)
from allbrain.soft_repair.alpha_controller import AlphaController
from allbrain.soft_repair.stability_adapter import StabilityAdapter


class PolicyBlender:
    """Blends old and new policy data by stability-weighted alpha.

    final = α × new + (1 - α) × old

    Numeric strategy_preferences, urgency_multipliers are blended.
    """

    def __init__(self) -> None:
        self._alpha_controller = AlphaController()
        self._stability_adapter = StabilityAdapter()

    def blend(
        self,
        old_policy_id: str,
        new_policy_id: str,
        fault_type: str,
        old_data: dict[str, Any],
        new_data: dict[str, Any],
        stability_score: float,
    ) -> BlendedPolicy | None:
        alpha = self._alpha_controller.compute(stability_score)

        blended_data = _blend_dicts(old_data, new_data, alpha)

        return BlendedPolicy(
            old_policy_id=old_policy_id,
            new_policy_id=new_policy_id,
            fault_type=fault_type,
            old_weight=1.0 - alpha,
            new_weight=alpha,
            blended_data=blended_data,
            stability_score=stability_score,
        )

    def should_blend(self, stability_score: float) -> bool:
        return self._stability_adapter.should_blend(stability_score)


def _blend_dicts(
    old: dict[str, Any],
    new: dict[str, Any],
    alpha: float,
) -> dict[str, Any]:
    """Blend numeric values: result = alpha * new + (1 - alpha) * old.
    Non-numeric values fall back to new.
    """
    result: dict[str, Any] = {}
    all_keys = set(old) | set(new)
    for key in all_keys:
        ov = old.get(key)
        nv = new.get(key)
        if isinstance(ov, (int, float)) and isinstance(nv, (int, float)):
            result[key] = alpha * nv + (1.0 - alpha) * ov
        elif nv is not None:
            result[key] = nv
        else:
            result[key] = ov
    return result
