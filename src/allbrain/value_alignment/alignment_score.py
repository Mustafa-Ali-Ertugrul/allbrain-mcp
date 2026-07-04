from __future__ import annotations

from allbrain.value_alignment.model import (
    ALIGNMENT_CHECK_INTERVAL,
    ALIGNMENT_THRESHOLD,
    AlignmentResult,
)


class AlignmentScoreTracker:
    """Tracks alignment over time. Detects when alignment drifts below threshold."""

    #: Minimum history length required for oscillation detection.
    _OSCILLATION_WINDOW = 6

    def __init__(self) -> None:
        self._history: dict[str, list[float]] = {}
        self._cycle_counter: int = 0

    def record(self, result: AlignmentResult) -> None:
        self._cycle_counter += 1
        key = result.score.fault_type
        self._history.setdefault(key, [])
        self._history[key].append(result.score.overall_score)
        if len(self._history[key]) > 30:
            self._history[key] = self._history[key][-30:]

    def is_aligned(self, fault_type: str) -> bool:
        buf = self._history.get(fault_type, [])
        if len(buf) < 5:
            return True
        avg = sum(buf[-5:]) / 5
        return avg >= ALIGNMENT_THRESHOLD

    def detect_oscillation(self, fault_type: str) -> bool:
        """Detect if the last N scores alternate between high and low (oscillation).

        Oscillation is defined as at least 3 direction changes in the last
        ``_OSCILLATION_WINDOW`` scores, indicating the constraint keeps flipping
        between pass and fail — a hallmark of live-lock.
        """
        buf = self._history.get(fault_type, [])
        if len(buf) < self._OSCILLATION_WINDOW:
            return False
        recent = buf[-self._OSCILLATION_WINDOW :]
        # Count direction changes: number of times diff flips sign
        changes = 0
        for i in range(1, len(recent) - 1):
            d1 = recent[i] - recent[i - 1]
            d2 = recent[i + 1] - recent[i]
            if d1 * d2 < 0:  # opposite signs → direction change
                changes += 1
        return changes >= 3

    def should_recheck(self) -> bool:
        return self._cycle_counter % ALIGNMENT_CHECK_INTERVAL == 0
