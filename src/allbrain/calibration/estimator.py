from __future__ import annotations

import hashlib
from collections.abc import Iterable

CALIBRATION_TEMPLATE_VERSION = 1


def _stable_calibration_id(context_key: str, event_ids: Iterable[str] | None = None) -> str:
    """Deterministic calibration id derived from context + sorted event ids.

    Same context + same event ids -> same id (replay-safe).
    Different event ids -> different id (per-computation unique).
    """
    if event_ids is None:
        event_ids = []
    event_key = "|".join(sorted(str(eid) for eid in event_ids))
    digest = hashlib.sha256(f"{context_key}:{event_key}".encode()).digest()
    return f"calibration-{digest.hex()[:12]}"


def squared_error(confidence: float, outcome: bool) -> float:
    """(confidence - (1.0 if outcome else 0.0))**2.

    Brier-style squared error per sample.
    """
    target = 1.0 if outcome else 0.0
    raw = float(confidence) - target
    return raw * raw


def mean_calibration_error(samples: list[tuple[float, bool]]) -> float:
    """Mean of squared_error over samples.

    Returns 0.0 for empty list (Sprint 47 default: no data = no error).
    """
    if not samples:
        return 0.0
    total = 0.0
    for confidence, outcome in samples:
        total += squared_error(confidence, outcome)
    return total / len(samples)


def mean_confidence(samples: list[tuple[float, bool]]) -> float:
    """Mean of predicted confidences. Returns 0.0 for empty list."""
    if not samples:
        return 0.0
    total = 0.0
    for confidence, _outcome in samples:
        total += float(confidence)
    return total / len(samples)


def accuracy(samples: list[tuple[float, bool]]) -> float:
    """Fraction correct: predicted >= 0.5 matches outcome.

    Returns 0.0 for empty list.
    """
    if not samples:
        return 0.0
    correct = 0
    for confidence, outcome in samples:
        predicted_positive = float(confidence) >= 0.5
        if predicted_positive == bool(outcome):
            correct += 1
    return correct / len(samples)


def calibrated_trust(trust_score: float, calibration_error: float) -> float:
    """Calibrated trust = trust_score × (1 - calibration_error), clamped [0, 1].

    Clamp is mandatory: trust_score is already in [0, 1], but future
    calibration models may produce unbounded error values, so the
    output is hard-clamped to keep the snapshot invariant safe.
    """
    raw = float(trust_score) * (1.0 - float(calibration_error))
    return max(0.0, min(1.0, raw))
