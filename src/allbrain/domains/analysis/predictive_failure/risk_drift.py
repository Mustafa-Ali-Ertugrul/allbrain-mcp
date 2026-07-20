from __future__ import annotations

DRIFT_MIN_SAMPLES = 3
DRIFT_WINDOW_SIZE = 10
DRIFT_BOOST_THRESHOLD = 0.15
DRIFT_MAX_BOOST = 0.20


class RiskDriftDetector:
    """Tracks risk scores over time to detect upward drift.

    Optional extension: if risk is increasing over time without a
    failure occurring, this provides an early-warning boost to the
    prediction level.

    Uses simple linear regression over a sliding window to compute
    the trend (slope) per fault type.
    """

    def __init__(self, window_size: int = DRIFT_WINDOW_SIZE) -> None:
        self._window_size = window_size
        self._history: dict[str, list[tuple[float, float]]] = {}

    def ingest(
        self,
        fault_type: str,
        risk_score: float,
        timestamp: float | None = None,
    ) -> None:
        """Record a risk score for a fault type at a given time.

        Keeps only the last N samples (sliding window).
        """
        if fault_type not in self._history:
            self._history[fault_type] = []
        self._history[fault_type].append((risk_score, timestamp or 0.0))
        if len(self._history[fault_type]) > self._window_size:
            self._history[fault_type] = self._history[fault_type][-self._window_size :]

    def compute_drift(self, fault_type: str) -> float:
        """Compute the drift (slope) for a fault type.

        Returns float in [-1, 1] where positive = increasing risk.
        Uses simple least-squares linear regression over the sliding
        window. Returns 0.0 if insufficient data (< DRIFT_MIN_SAMPLES).
        """
        samples = self._history.get(fault_type, [])
        if len(samples) < DRIFT_MIN_SAMPLES:
            return 0.0

        scores = [s[0] for s in samples]
        n = len(scores)
        xs = list(range(n))
        mean_x = sum(xs) / n
        mean_y = sum(scores) / n

        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, scores, strict=False))
        denominator = sum((x - mean_x) ** 2 for x in xs)

        if denominator == 0:
            return 0.0

        slope = numerator / denominator
        # Normalize: max possible per-step change is 1.0
        normalized = slope / 1.0
        return max(-1.0, min(1.0, normalized))

    def get_drift_boost(self, fault_type: str, current_risk: float) -> float:
        """Return a boost in [0, DRIFT_MAX_BOOST] if upward drift detected.

        Only activates when:
        - Drift slope > DRIFT_BOOST_THRESHOLD (significant upward trend)
        - current_risk >= 0.40 (non-trivial risk level)
        """
        drift = self.compute_drift(fault_type)
        if drift > DRIFT_BOOST_THRESHOLD and current_risk >= 0.40:
            return min(DRIFT_MAX_BOOST, drift * 0.5)
        return 0.0

    def clear(self, fault_type: str) -> None:
        """Reset history for a fault type (e.g., after failure avoided)."""
        self._history.pop(fault_type, None)

    def clear_all(self) -> None:
        """Reset all history."""
        self._history.clear()

    @property
    def history(self) -> dict[str, list[tuple[float, float]]]:
        """Return a copy of the current drift history."""
        return dict(self._history)
