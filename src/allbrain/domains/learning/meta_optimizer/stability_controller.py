from __future__ import annotations

from typing import TYPE_CHECKING

from allbrain.domains.learning.meta_optimizer.model import META_OPTIMIZER_MIN_STABILITY

if TYPE_CHECKING:
    from allbrain.domains.learning.coevolution.oscillation_detector import OscillationDetector


class StabilityController:
    """Guards meta-optimizer updates when overall stability is low.

    Blocks updates when the stability score falls below a configurable
    threshold *or* when an attached OscillationDetector reports active
    oscillation for the relevant fault type. This closes the dead-zone
    where stability is nominally above threshold but the co-evolution
    feedback loop is oscillating.

    Contract:
        - allow_update(stability_score) preserves backward-compatible
          behavior (threshold-only gating).
        - allow_update(stability_score, oscillation_detector=det,
          fault_type=ft) additionally blocks when det.is_oscillating(ft)
          is True.

    Errors:
        None raised; returns False on block conditions.

    Examples:
        >>> ctrl = StabilityController()
        >>> ctrl.allow_update(0.55)
        True
        >>> ctrl.allow_update(0.30)
        False

    Edges:
        Works in conjunction with WeightOptimizer and
        PredictiveFailureManager._run_weight_optimizer.

    Relations:
        OscillationDetector (source of oscillation signals),
        META_OPTIMIZER_MIN_STABILITY (default threshold).
    """

    def __init__(self, min_stability: float = META_OPTIMIZER_MIN_STABILITY) -> None:
        self.min_stability = min_stability

    def allow_update(
        self,
        stability_score: float,
        *,
        oscillation_detector: OscillationDetector | None = None,
        fault_type: str | None = None,
    ) -> bool:
        """Decide whether a meta-optimizer weight update is allowed.

        Args:
            stability_score: Current system stability metric in [0, 1].
            oscillation_detector: Optional detector that tracks co-evolution
                feedback-loop oscillation. When provided together with
                fault_type, an active oscillation blocks the update even
                if stability_score >= min_stability.
            fault_type: Fault-type key passed to the oscillation detector.
                Required when oscillation_detector is provided.

        Returns:
            True if the update may proceed, False if blocked by low
            stability or active oscillation.
        """
        oscillation_blocked = (
            oscillation_detector is not None
            and fault_type is not None
            and oscillation_detector.is_oscillating(fault_type)
        )
        return stability_score >= self.min_stability and not oscillation_blocked
