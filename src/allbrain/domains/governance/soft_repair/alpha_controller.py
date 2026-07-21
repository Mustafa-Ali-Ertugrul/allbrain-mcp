from __future__ import annotations

from allbrain.domains.governance.soft_repair.model import BLEND_ALPHA_MAX, BLEND_ALPHA_MIN


class AlphaController:
    """Determines blend weight α from stability score.

    α = NEW policy weight.
    α = clamp(stability_score, BLEND_ALPHA_MIN, BLEND_ALPHA_MAX)

    Low stability → low α → old policy dominates (conservative).
    High stability → high α → new policy dominates (fast learning).
    """

    def compute(self, stability_score: float) -> float:
        if stability_score <= 0.0:
            return BLEND_ALPHA_MIN
        if stability_score >= 1.0:
            return BLEND_ALPHA_MAX
        return max(BLEND_ALPHA_MIN, min(BLEND_ALPHA_MAX, stability_score))
