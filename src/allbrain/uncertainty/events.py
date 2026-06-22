from __future__ import annotations


UNCERTAINTY_COMPUTED_TEMPLATE_VERSION = 1

REQUIRED_KEYS: frozenset[str] = frozenset(
    {"context_key", "uncertainty", "confidence_interval", "evidence_count"}
)


def validate_payload(payload: dict) -> None:
    if not REQUIRED_KEYS.issubset(payload.keys()):
        raise ValueError(f"payload missing keys: {REQUIRED_KEYS - set(payload.keys())}")
    context_key = payload.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        raise ValueError("context_key must be a non-empty string")
    for key in ("uncertainty", "confidence_interval"):
        value = payload.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be numeric")
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{key} must be in [0, 1], got {value}")
    evidence_count = payload.get("evidence_count")
    if not isinstance(evidence_count, int) or evidence_count < 0:
        raise ValueError("evidence_count must be a non-negative int")


def make_payload(
    *,
    context_key: str,
    uncertainty: float,
    confidence_interval: float,
    evidence_count: int,
) -> dict:
    payload = {
        "context_key": str(context_key),
        "uncertainty": float(uncertainty),
        "confidence_interval": float(confidence_interval),
        "evidence_count": int(evidence_count),
        "template_version": UNCERTAINTY_COMPUTED_TEMPLATE_VERSION,
    }
    validate_payload(payload)
    return payload
