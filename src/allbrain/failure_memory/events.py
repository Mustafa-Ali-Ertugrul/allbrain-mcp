from __future__ import annotations

from typing import Any

from allbrain.failure_memory.model import FAILURE_MEMORY_TEMPLATE_VERSION

MEMORY_STORED_KEYS: frozenset[str] = frozenset(
    {"fault_type", "strategy", "success", "severity", "occurred_at", "failure_count"}
)
MEMORY_RETRIEVED_KEYS: frozenset[str] = frozenset(
    {"fault_type", "total_records", "experience_count"}
)
PATTERN_DETECTED_KEYS: frozenset[str] = frozenset(
    {"fault_type", "strategy", "success_rate", "attempts", "severity"}
)
EXPERIENCE_UPDATED_KEYS: frozenset[str] = frozenset(
    {"fault_type", "strategy", "success_rate", "attempts"}
)
LEARNING_APPLIED_KEYS: frozenset[str] = frozenset(
    {"fault_type", "strategy", "bias_value"}
)


def validate_failure_memory_stored(p: dict[str, Any]) -> None:
    m = MEMORY_STORED_KEYS - set(p.keys())
    if m:
        raise ValueError("failure_memory_stored missing: " + str(m))
    if not isinstance(p.get("fault_type"), str):
        raise ValueError("fault_type must be str")
    if not isinstance(p.get("strategy"), str):
        raise ValueError("strategy must be str")
    if not isinstance(p.get("success"), bool):
        raise ValueError("success must be bool")
    if not isinstance(p.get("severity"), str):
        raise ValueError("severity must be str")
    occurred_at = p.get("occurred_at")
    if not isinstance(occurred_at, (int, float)):
        raise ValueError("occurred_at must be numeric")
    if not isinstance(p.get("failure_count"), int):
        raise ValueError("failure_count must be int")


def validate_failure_memory_retrieved(p: dict[str, Any]) -> None:
    m = MEMORY_RETRIEVED_KEYS - set(p.keys())
    if m:
        raise ValueError("failure_memory_retrieved missing: " + str(m))
    if not isinstance(p.get("fault_type"), str):
        raise ValueError("fault_type must be str")
    if not isinstance(p.get("total_records"), int):
        raise ValueError("total_records must be int")
    if not isinstance(p.get("experience_count"), int):
        raise ValueError("experience_count must be int")


def validate_failure_pattern_detected(p: dict[str, Any]) -> None:
    m = PATTERN_DETECTED_KEYS - set(p.keys())
    if m:
        raise ValueError("failure_pattern_detected missing: " + str(m))
    if not isinstance(p.get("fault_type"), str):
        raise ValueError("fault_type must be str")
    if not isinstance(p.get("strategy"), str):
        raise ValueError("strategy must be str")
    rate = p.get("success_rate")
    if not isinstance(rate, (int, float)):
        raise ValueError("success_rate must be numeric")
    if not (0.0 <= float(rate) <= 1.0):
        raise ValueError("success_rate must be in [0, 1]")
    if not isinstance(p.get("attempts"), int):
        raise ValueError("attempts must be int")


def validate_recovery_experience_updated(p: dict[str, Any]) -> None:
    m = EXPERIENCE_UPDATED_KEYS - set(p.keys())
    if m:
        raise ValueError("recovery_experience_updated missing: " + str(m))
    if not isinstance(p.get("fault_type"), str):
        raise ValueError("fault_type must be str")
    if not isinstance(p.get("strategy"), str):
        raise ValueError("strategy must be str")
    rate = p.get("success_rate")
    if not isinstance(rate, (int, float)):
        raise ValueError("success_rate must be numeric")
    if not (0.0 <= float(rate) <= 1.0):
        raise ValueError("success_rate must be in [0, 1]")
    if not isinstance(p.get("attempts"), int):
        raise ValueError("attempts must be int")


def validate_recovery_learning_applied(p: dict[str, Any]) -> None:
    m = LEARNING_APPLIED_KEYS - set(p.keys())
    if m:
        raise ValueError("recovery_learning_applied missing: " + str(m))
    if not isinstance(p.get("fault_type"), str):
        raise ValueError("fault_type must be str")
    if not isinstance(p.get("strategy"), str):
        raise ValueError("strategy must be str")
    bias = p.get("bias_value")
    if not isinstance(bias, (int, float)):
        raise ValueError("bias_value must be numeric")
    if not (0.0 <= float(bias) <= 1.0):
        raise ValueError("bias_value must be in [0, 1]")


def make_failure_memory_stored_payload(
    *,
    fault_type: str,
    strategy: str,
    success: bool,
    severity: str,
    occurred_at: float,
    failure_count: int,
    tv: int = FAILURE_MEMORY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "strategy": strategy,
        "success": success,
        "severity": severity,
        "occurred_at": occurred_at,
        "failure_count": failure_count,
        "template_version": tv,
    }
    validate_failure_memory_stored(p)
    return p


def make_failure_memory_retrieved_payload(
    *,
    fault_type: str,
    total_records: int,
    experience_count: int,
    tv: int = FAILURE_MEMORY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "total_records": total_records,
        "experience_count": experience_count,
        "template_version": tv,
    }
    validate_failure_memory_retrieved(p)
    return p


def make_failure_pattern_detected_payload(
    *,
    fault_type: str,
    strategy: str,
    success_rate: float,
    attempts: int,
    severity: str,
    tv: int = FAILURE_MEMORY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "strategy": strategy,
        "success_rate": success_rate,
        "attempts": attempts,
        "severity": severity,
        "template_version": tv,
    }
    validate_failure_pattern_detected(p)
    return p


def make_recovery_experience_updated_payload(
    *,
    fault_type: str,
    strategy: str,
    success_rate: float,
    attempts: int,
    tv: int = FAILURE_MEMORY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "strategy": strategy,
        "success_rate": success_rate,
        "attempts": attempts,
        "template_version": tv,
    }
    validate_recovery_experience_updated(p)
    return p


def make_recovery_learning_applied_payload(
    *,
    fault_type: str,
    strategy: str,
    bias_value: float,
    tv: int = FAILURE_MEMORY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "strategy": strategy,
        "bias_value": bias_value,
        "template_version": tv,
    }
    validate_recovery_learning_applied(p)
    return p