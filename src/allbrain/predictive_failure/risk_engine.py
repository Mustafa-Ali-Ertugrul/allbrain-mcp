from __future__ import annotations

from allbrain.predictive_failure.model import RiskSignal, SIGNAL_TO_FAULT_TYPE


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _frequency_weight(frequency: int) -> float:
    if frequency >= 5:
        return 1.0
    if frequency >= 3:
        return 0.7
    if frequency >= 1:
        return 0.4
    return 0.0


class RiskEngine:
    """Deterministic risk computation engine.

    Groups signals by fault type and computes a blended risk score
    from severity * frequency-weight, using 70% max + 30% mean.
    """

    @staticmethod
    def compute_risk(signals: list[RiskSignal]) -> dict[str, float]:
        """Compute risk scores per fault type.

        Returns dict mapping fault_type -> risk_score ∈ [0, 1].
        Returns empty dict for empty input.
        """
        if not signals:
            return {}

        groups: dict[str, list[float]] = {}
        for signal in signals:
            ft = SIGNAL_TO_FAULT_TYPE.get(signal.signal_type, signal.signal_type)
            weighted = _clamp(signal.severity) * _frequency_weight(signal.frequency)
            groups.setdefault(ft, []).append(weighted)

        result: dict[str, float] = {}
        for fault_type, weighted_severities in groups.items():
            if not weighted_severities:
                continue
            max_w = max(weighted_severities)
            mean_w = sum(weighted_severities) / len(weighted_severities)
            risk = _clamp(max_w * 0.7 + mean_w * 0.3)
            result[fault_type] = risk

        return result
