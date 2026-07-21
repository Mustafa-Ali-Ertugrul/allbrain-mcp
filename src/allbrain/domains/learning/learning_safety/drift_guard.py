from __future__ import annotations

from collections import deque

from allbrain.domains.learning.learning_safety.model import (
    DRIFT_THRESHOLD,
    SAFETY_LEARNING_DRIFT_DETECTED,
    SafetyEvent,
)


class DriftGuard:
    """Detects anomalous drops in strategy effectiveness over time.

    Tracks recent (strategy, effectiveness) records in a fixed-size window.
    When the second half's average effectiveness drops below the first
    half's by more than DRIFT_THRESHOLD, emits a drift SafetyEvent.
    """

    def __init__(
        self,
        window_size: int = 6,
        drift_threshold: float = DRIFT_THRESHOLD,
    ) -> None:
        if window_size < 4:
            raise ValueError("window_size must be >= 4")
        # Snap to even so we can split halves cleanly
        if window_size % 2 != 0:
            window_size += 1
        self._window_size = window_size
        self._threshold = drift_threshold
        self._records: deque[tuple[str, float]] = deque(maxlen=window_size)
        self._fault_type: str = ""
        self._signal_type: str = ""

    def configure(self, fault_type: str, signal_type: str) -> None:
        """Set the current fault/signal context for the next batch."""
        self._fault_type = fault_type
        self._signal_type = signal_type

    def record(self, strategy: str, effectiveness: float) -> SafetyEvent | None:
        """Record one (strategy, effectiveness) observation.

        Returns a SafetyEvent if drift is detected, else None.
        """
        self._records.append((strategy, effectiveness))
        if len(self._records) < self._window_size:
            return None

        effs = [e for _, e in self._records]
        half = self._window_size // 2
        first_avg = sum(effs[:half]) / half
        second_avg = sum(effs[half:]) / half
        drop = first_avg - second_avg

        if drop > self._threshold:
            event = SafetyEvent(
                event_type=SAFETY_LEARNING_DRIFT_DETECTED,
                fault_type=self._fault_type,
                signal_type=self._signal_type,
                metric_value=second_avg,
                threshold=self._threshold,
                details={
                    "first_half_avg": first_avg,
                    "second_half_avg": second_avg,
                    "drop": drop,
                    "window_size": self._window_size,
                },
            )
            self._records.clear()
            return event

        return None

    def reset(self) -> None:
        self._records.clear()
        self._fault_type = ""
        self._signal_type = ""

    @property
    def records_seen(self) -> int:
        return len(self._records)
