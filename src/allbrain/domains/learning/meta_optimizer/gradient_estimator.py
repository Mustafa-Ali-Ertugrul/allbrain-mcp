from __future__ import annotations

from allbrain.domains.learning.meta_optimizer.model import META_OPTIMIZER_LEARNING_RATE
from allbrain.domains.learning.meta_scoring.model import ScoringProfile


class GradientEstimator:
    """Estimates a reward gradient per metric from outcome deltas.

    gradient[m] = learning_rate * (delta[m] / max_delta) * (1 - profile_weight[m] + 0.2)
    Positive delta → increase weight. Negative delta → decrease weight.
    """

    def estimate(
        self,
        profile: ScoringProfile,
        delta_success: float,
        delta_risk: float,
        delta_stability: float,
        delta_drift: float,
    ) -> dict[str, float]:
        raw = {
            "success_weight": delta_success,
            "risk_weight": delta_risk,
            "stability_weight": delta_stability,
            "drift_weight": delta_drift,
        }

        max_abs = max(abs(v) for v in raw.values())
        if max_abs < 1e-6:
            return {"success_weight": 0.0, "risk_weight": 0.0, "stability_weight": 0.0, "drift_weight": 0.0}

        gradient: dict[str, float] = {}
        for key, delta in raw.items():
            current = getattr(profile, key)
            gradient[key] = META_OPTIMIZER_LEARNING_RATE * (delta / max_abs) * (1.0 - current + 0.2)

        return gradient
