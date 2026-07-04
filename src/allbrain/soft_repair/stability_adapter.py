from __future__ import annotations

from allbrain.soft_repair.model import DEFAULT_BLEND_THRESHOLD, HARD_UPDATE_THRESHOLD


class StabilityAdapter:
    """Decides whether to apply soft blend or hard update based on stability.

    - stability >= HARD_UPDATE_THRESHOLD: hard update (full replacement)
    - stability < DEFAULT_BLEND_THRESHOLD: soft blend needed
    """

    def should_blend(
        self,
        stability_score: float,
        threshold: float = DEFAULT_BLEND_THRESHOLD,
    ) -> bool:
        return stability_score < threshold

    def allow_hard_update(self, stability_score: float) -> bool:
        return stability_score >= HARD_UPDATE_THRESHOLD
