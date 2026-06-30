from __future__ import annotations

from allbrain.meta_optimizer.model import META_OPTIMIZER_MIN_STABILITY


class StabilityController:
    """Guards meta-optimizer updates when overall stability is low.

    If stability < MIN_STABILITY, no update is applied.
    This prevents the optimizer from reacting to noisy/unstable
    policy performance.
    """

    def allow_update(self, stability_score: float) -> bool:
        return stability_score >= META_OPTIMIZER_MIN_STABILITY
