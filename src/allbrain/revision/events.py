from __future__ import annotations

from allbrain.revision.policies import REVISION_TEMPLATE_VERSION

REVISION_REASON_CONTRADICTION = "contradiction"

REQUIRED_KEYS: frozenset[str] = frozenset(
    {"context_key", "old_confidence", "new_confidence", "reason", "evidence_count"}
)


def validate_payload(payload: dict) -> None:
    if not REQUIRED_KEYS.issubset(payload.keys()):
        raise ValueError(f"payload missing keys: {REQUIRED_KEYS - set(payload.keys())}")
    context_key = payload.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        raise ValueError("context_key must be a non-empty string")
    for key in ("old_confidence", "new_confidence"):
        value = payload.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be numeric")
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{key} must be in [0, 1], got {value}")
    reason = payload.get("reason")
    if reason != REVISION_REASON_CONTRADICTION:
        raise ValueError(f"unknown reason: {reason}")
    evidence_count = payload.get("evidence_count")
    if not isinstance(evidence_count, int) or evidence_count < 0:
        raise ValueError("evidence_count must be a non-negative int")


def make_payload(
    *,
    context_key: str,
    old_confidence: float,
    new_confidence: float,
    reason: str,
    evidence_count: int,
) -> dict:
    payload = {
        "context_key": str(context_key),
        "old_confidence": float(old_confidence),
        "new_confidence": float(new_confidence),
        "reason": str(reason),
        "evidence_count": int(evidence_count),
        "template_version": REVISION_TEMPLATE_VERSION,
    }
    validate_payload(payload)
    return payload
