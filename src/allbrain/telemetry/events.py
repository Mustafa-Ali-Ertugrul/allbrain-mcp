from __future__ import annotations

from allbrain.telemetry.model import TELEMETRY_TEMPLATE_VERSION

STARTED_REQUIRED_KEYS: frozenset[str] = frozenset({"agent_id", "task_id", "tool_name"})
COMPLETED_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_id", "tool_name", "duration_ms", "success", "retry_count"}
)
RUNTIME_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"agent_id", "mean_duration_ms", "success_rate", "mean_retry_count", "runtime_score"}
)


def validate_started_payload(payload: dict) -> None:
    missing = STARTED_REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise ValueError("started payload missing: " + str(missing))
    for field in ("agent_id", "task_id", "tool_name"):
        val = payload.get(field)
        if not isinstance(val, str) or not val:
            raise ValueError(field + " must be a non-empty string")


def validate_completed_payload(payload: dict) -> None:
    missing = COMPLETED_REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise ValueError("completed payload missing: " + str(missing))
    for field in ("agent_id", "task_id", "tool_name"):
        val = payload.get(field)
        if not isinstance(val, str) or not val:
            raise ValueError(field + " must be non-empty string")
    duration_ms = payload.get("duration_ms")
    if not isinstance(duration_ms, (int, float)) or float(duration_ms) < 0:
        raise ValueError("duration_ms must be non-negative, got " + str(duration_ms))
    if not isinstance(payload.get("success"), bool):
        raise ValueError("success must be bool")
    retry_count = payload.get("retry_count")
    if not isinstance(retry_count, (int, float)) or float(retry_count) < 0:
        raise ValueError("retry_count must be non-negative, got " + str(retry_count))


def validate_runtime_payload(payload: dict) -> None:
    missing = RUNTIME_REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise ValueError("runtime payload missing: " + str(missing))
    if not isinstance(payload.get("agent_id"), str) or not payload["agent_id"]:
        raise ValueError("agent_id must be non-empty string")
    for field in ("mean_duration_ms", "success_rate", "mean_retry_count", "runtime_score"):
        val = payload.get(field)
        if not isinstance(val, (int, float)) or not 0.0 <= float(val) <= 1.0:
            raise ValueError(field + " must be in [0,1], got " + str(val))


def make_started_payload(
    *,
    agent_id: str,
    task_id: str,
    tool_name: str,
    template_version: int = TELEMETRY_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_id": str(task_id),
        "tool_name": str(tool_name),
        "template_version": int(template_version),
    }
    validate_started_payload(p)
    return p


def make_completed_payload(
    *,
    agent_id: str,
    task_id: str,
    tool_name: str,
    duration_ms: float,
    success: bool,
    retry_count: float,
    template_version: int = TELEMETRY_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_id": str(task_id),
        "tool_name": str(tool_name),
        "duration_ms": float(duration_ms),
        "success": bool(success),
        "retry_count": float(retry_count),
        "template_version": int(template_version),
    }
    validate_completed_payload(p)
    return p


def make_runtime_updated_payload(
    *,
    agent_id: str,
    mean_duration_ms: float,
    success_rate: float,
    mean_retry_count: float,
    runtime_score_val: float,
    template_version: int = TELEMETRY_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "mean_duration_ms": float(mean_duration_ms),
        "success_rate": float(success_rate),
        "mean_retry_count": float(mean_retry_count),
        "runtime_score": float(runtime_score_val),
        "template_version": int(template_version),
    }
    validate_runtime_payload(p)
    return p
