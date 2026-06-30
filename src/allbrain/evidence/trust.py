from __future__ import annotations

from collections.abc import Iterable


def trust_score(evidence_weights: Iterable[float]) -> float:
    """Sprint 46 trust score: arithmetic mean of evidence weights, clamped [0, 1].

    Returns 1.0 if no evidence weights are provided (Sprint 46 decision:
    missing trust defaults to full confidence, not zero — "bilinçsiz
    default çöküş" avoidance).
    """
    weights = [float(w) for w in evidence_weights]
    if not weights:
        return 1.0
    return max(0.0, min(1.0, sum(weights) / len(weights)))
