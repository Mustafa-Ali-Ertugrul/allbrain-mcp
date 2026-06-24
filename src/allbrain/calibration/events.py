from __future__ import annotations

from allbrain.calibration.estimator import CALIBRATION_TEMPLATE_VERSION


REQUIRED_KEYS: frozenset[str] = frozenset(
    {"context_key", "predicted_confidence", "actual_outcome"}
)


def validate_payload(payload: dict) -> None:
    if not REQUIRED_KEYS.issubset(payload.keys()):
        raise ValueError(f"payload missing keys: {REQUIRED_KEYS - set(payload.keys())}")
    context_key = payload.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        raise ValueError("context_key must be a non-empty string")
    predicted = payload.get("predicted_confidence")
    if not isinstance(predicted, (int, float)):
        raise ValueError("predicted_confidence must be numeric")
    if not 0.0 <= float(predicted) <= 1.0:
        raise ValueError(f"predicted_confidence must be in [0, 1], got {predicted}")
    outcome = payload.get("actual_outcome")
    if not isinstance(outcome, bool):
        raise ValueError("actual_outcome must be a bool")


def make_payload(
    *,
    context_key: str,
    predicted_confidence: float,
    actual_outcome: bool,
    template_version: int = CALIBRATION_TEMPLATE_VERSION,
) -> dict:
    payload = {
        "context_key": str(context_key),
        "predicted_confidence": float(predicted_confidence),
        "actual_outcome": bool(actual_outcome),
        "template_version": int(template_version),
    }
    validate_payload(payload)
    return payload
