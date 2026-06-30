from __future__ import annotations

from allbrain.coevolution.model import COEVOLUTION_OSCILLATION_THRESHOLD, COEVOLUTION_WINDOW_SIZE


class OscillationDetector:
    """Detects when the co-evolution feedback loop oscillates.

    Tracks stddev of recent score_delta over rolling window.
    If stddev > OSCILLATION_THRESHOLD → oscillation detected.
    """

    def __init__(self) -> None:
        self._deltas: dict[str, list[float]] = {}

    def record(self, fault_type: str, delta: float) -> None:
        self._deltas.setdefault(fault_type, [])
        buf = self._deltas[fault_type]
        buf.append(delta)
        if len(buf) > COEVOLUTION_WINDOW_SIZE:
            buf.pop(0)

    def is_oscillating(self, fault_type: str) -> bool:
        buf = self._deltas.get(fault_type, [])
        if len(buf) < 4:
            return False
        mean = sum(buf) / len(buf)
        variance = sum((d - mean) ** 2 for d in buf) / len(buf)
        return (variance ** 0.5) > COEVOLUTION_OSCILLATION_THRESHOLD

    def oscillation_index(self, fault_type: str) -> float:
        buf = self._deltas.get(fault_type, [])
        if len(buf) < 4:
            return 0.0
        mean = sum(buf) / len(buf)
        variance = sum((d - mean) ** 2 for d in buf) / len(buf)
        return min(1.0, (variance ** 0.5) / COEVOLUTION_OSCILLATION_THRESHOLD)

    def clear(self) -> None:
        self._deltas.clear()
