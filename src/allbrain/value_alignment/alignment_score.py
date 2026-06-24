from __future__ import annotations

from allbrain.value_alignment.model import AlignmentScore, AlignmentResult, ALIGNMENT_THRESHOLD, ALIGNMENT_CHECK_INTERVAL


class AlignmentScoreTracker:
    """Tracks alignment over time. Detects when alignment drifts below threshold."""

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

    def should_recheck(self) -> bool:
        return self._cycle_counter % ALIGNMENT_CHECK_INTERVAL == 0