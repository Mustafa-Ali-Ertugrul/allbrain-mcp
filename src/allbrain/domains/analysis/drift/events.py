from __future__ import annotations

from allbrain.domains.analysis.drift.detector import DRIFT_TEMPLATE_VERSION, REASONS

REQUIRED_KEYS: frozenset[str] = frozenset({"context_key", "belief_before", "belief_after", "magnitude", "reason"})


def validate_payload(payload: dict) -> None:
    if not REQUIRED_KEYS.issubset(payload.keys()):
        raise ValueError(f"payload missing keys: {REQUIRED_KEYS - set(payload.keys())}")
    context_key = payload.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        raise ValueError("context_key must be a non-empty string")
    for key in ("belief_before", "belief_after"):
        value = payload.get(key)
        if not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be numeric")
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{key} must be in [0, 1], got {value}")
    magnitude = payload.get("magnitude")
    if not isinstance(magnitude, (int, float)):
        raise ValueError("magnitude must be numeric")
    if float(magnitude) < 0.0:
        raise ValueError(f"magnitude must be non-negative, got {magnitude}")
    reason = payload.get("reason")
    if reason not in REASONS:
        raise ValueError(f"unknown drift reason: {reason!r} (expected one of {sorted(REASONS)})")
    expected_magnitude = abs(float(payload["belief_after"]) - float(payload["belief_before"]))
    if abs(float(magnitude) - expected_magnitude) > 1e-9:
        raise ValueError(f"magnitude {magnitude} does not match |after - before| = {expected_magnitude}")


def make_payload(
    *,
    context_key: str,
    belief_before: float,
    belief_after: float,
    reason: str,
    template_version: int = DRIFT_TEMPLATE_VERSION,
) -> dict:
    before = float(belief_before)
    after = float(belief_after)
    magnitude = abs(after - before)
    payload = {
        "context_key": str(context_key),
        "belief_before": before,
        "belief_after": after,
        "magnitude": float(magnitude),
        "reason": str(reason),
        "template_version": int(template_version),
    }
    validate_payload(payload)
    return payload
