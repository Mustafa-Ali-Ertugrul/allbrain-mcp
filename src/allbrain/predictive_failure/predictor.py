from __future__ import annotations

from allbrain.predictive_failure.model import (
    FailurePrediction,
    LEVEL_SAFE,
    LEVEL_WARNING,
    LEVEL_FAILURE,
    RISK_THRESHOLD_WARNING,
    RISK_THRESHOLD_FAILURE,
)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class Predictor:
    """Threshold-based failure predictor.

    Maps a continuous risk score to a discrete prediction level:
      - >= 0.70 → FAILURE (confidence 0.9)
      - >= 0.40 → WARNING (confidence 0.7)
      - < 0.40  → SAFE (confidence 0.5)
    """

    @staticmethod
    def predict(
        fault_id: str,
        fault_type: str,
        risk_score: float,
        top_signals: tuple[str, ...] = (),
    ) -> FailurePrediction:
        risk_score = _clamp(risk_score)

        if risk_score >= RISK_THRESHOLD_FAILURE:
            level = LEVEL_FAILURE
            confidence = 0.9
        elif risk_score >= RISK_THRESHOLD_WARNING:
            level = LEVEL_WARNING
            confidence = 0.7
        else:
            level = LEVEL_SAFE
            confidence = 0.5

        return FailurePrediction(
            fault_id=fault_id,
            fault_type=fault_type,
            probability=risk_score,
            confidence=confidence,
            top_signals=top_signals,
            level=level,
        )
