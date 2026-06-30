from __future__ import annotations

from allbrain.reputation.estimator import REPUTATION_TEMPLATE_VERSION

REQUIRED_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_id", "success", "confidence", "duration_ms", "retry_count"}
)


def validate_payload(payload: dict) -> None:
    if not REQUIRED_KEYS.issubset(payload.keys()):
        raise ValueError(f"payload missing keys: {REQUIRED_KEYS - set(payload.keys())}")
    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        raise ValueError("agent_id must be a non-empty string")
    task_id = payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("task_id must be a non-empty string")
    success = payload.get("success")
    if not isinstance(success, bool):
        raise ValueError("success must be a bool")
    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be numeric")
    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError(f"confidence must be in [0, 1], got {confidence}")
    duration_ms = payload.get("duration_ms")
    if not isinstance(duration_ms, (int, float)):
        raise ValueError("duration_ms must be numeric")
    if float(duration_ms) < 0:
        raise ValueError(f"duration_ms must be >= 0, got {duration_ms}")
    retry_count = payload.get("retry_count")
    if not isinstance(retry_count, (int, float)):
        raise ValueError("retry_count must be numeric")
    if float(retry_count) < 0:
        raise ValueError(f"retry_count must be >= 0, got {retry_count}")


def make_payload(
    *,
    agent_id: str,
    task_id: str,
    success: bool,
    confidence: float,
    duration_ms: float,
    retry_count: float,
    reputation_score: float,
    analysis_id: str,
    template_version: int = REPUTATION_TEMPLATE_VERSION,
) -> dict:
    payload = {
        "agent_id": str(agent_id),
        "task_id": str(task_id),
        "success": bool(success),
        "confidence": float(confidence),
        "duration_ms": float(duration_ms),
        "retry_count": float(retry_count),
        "reputation_score": float(reputation_score),
        "analysis_id": str(analysis_id),
        "template_version": int(template_version),
    }
    validate_payload(payload)
    return payload
