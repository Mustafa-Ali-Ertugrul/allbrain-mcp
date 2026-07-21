from __future__ import annotations

from typing import Any

from allbrain.domains.governance.adaptive_recovery.model import (
    ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
)

CHAIN_CREATED_KEYS: frozenset[str] = frozenset(
    {
        "chain_id",
        "fault_id",
        "fault_type",
        "steps_count",
        "strategies",
    }
)
STEP_STARTED_KEYS: frozenset[str] = frozenset(
    {
        "chain_id",
        "fault_id",
        "strategy",
        "order",
        "step_index",
    }
)
STEP_FAILED_KEYS: frozenset[str] = frozenset(
    {
        "chain_id",
        "fault_id",
        "strategy",
        "order",
        "reason",
    }
)
STEP_SUCCEEDED_KEYS: frozenset[str] = frozenset(
    {
        "chain_id",
        "fault_id",
        "strategy",
        "order",
        "confidence",
    }
)
STRATEGY_SWITCHED_KEYS: frozenset[str] = frozenset(
    {
        "chain_id",
        "fault_id",
        "from_strategy",
        "to_strategy",
        "reason",
    }
)
ADAPTIVE_RECOVERY_COMPLETED_KEYS: frozenset[str] = frozenset(
    {
        "chain_id",
        "fault_id",
        "outcome",
        "steps_taken",
    }
)


def _check_keys(p: dict[str, Any], keys: frozenset[str], label: str) -> None:
    missing = keys - set(p.keys())
    if missing:
        raise ValueError(f"{label} missing: {missing}")


def _check_str(v: Any, label: str) -> str:
    if not isinstance(v, str):
        raise ValueError(f"{label} must be str, got {type(v).__name__}")
    return v


def _check_float_in_range(v: Any, label: str, lo: float = 0.0, hi: float = 1.0) -> float:
    if not isinstance(v, (int, float)):
        raise ValueError(f"{label} must be numeric, got {type(v).__name__}")
    f = float(v)
    if not (lo <= f <= hi):
        raise ValueError(f"{label} must be in [{lo}, {hi}], got {f}")
    return f


def _check_int_ge(v: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(v, int):
        raise ValueError(f"{label} must be int, got {type(v).__name__}")
    if v < minimum:
        raise ValueError(f"{label} must be >= {minimum}, got {v}")
    return v


def validate_chain_created(p: dict[str, Any]) -> None:
    _check_keys(p, CHAIN_CREATED_KEYS, "chain_created")
    _check_str(p["chain_id"], "chain_id")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["fault_type"], "fault_type")
    _check_int_ge(p["steps_count"], "steps_count", 0)
    strategies = p.get("strategies")
    if not isinstance(strategies, (list, tuple)):
        raise ValueError("strategies must be a list/tuple")


def validate_step_started(p: dict[str, Any]) -> None:
    _check_keys(p, STEP_STARTED_KEYS, "step_started")
    _check_str(p["chain_id"], "chain_id")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["strategy"], "strategy")
    _check_int_ge(p["order"], "order", 1)
    _check_int_ge(p["step_index"], "step_index", 0)


def validate_step_failed(p: dict[str, Any]) -> None:
    _check_keys(p, STEP_FAILED_KEYS, "step_failed")
    _check_str(p["chain_id"], "chain_id")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["strategy"], "strategy")
    _check_int_ge(p["order"], "order", 1)
    _check_str(p["reason"], "reason")


def validate_step_succeeded(p: dict[str, Any]) -> None:
    _check_keys(p, STEP_SUCCEEDED_KEYS, "step_succeeded")
    _check_str(p["chain_id"], "chain_id")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["strategy"], "strategy")
    _check_int_ge(p["order"], "order", 1)
    _check_float_in_range(p["confidence"], "confidence")


def validate_strategy_switched(p: dict[str, Any]) -> None:
    _check_keys(p, STRATEGY_SWITCHED_KEYS, "strategy_switched")
    _check_str(p["chain_id"], "chain_id")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["from_strategy"], "from_strategy")
    _check_str(p["to_strategy"], "to_strategy")
    _check_str(p["reason"], "reason")


def validate_adaptive_recovery_completed(p: dict[str, Any]) -> None:
    _check_keys(p, ADAPTIVE_RECOVERY_COMPLETED_KEYS, "adaptive_recovery_completed")
    _check_str(p["chain_id"], "chain_id")
    _check_str(p["fault_id"], "fault_id")
    outcome = _check_str(p["outcome"], "outcome")
    if outcome not in ("success", "failed", "escalated"):
        raise ValueError(f"outcome must be success/failed/escalated, got {outcome}")
    _check_int_ge(p["steps_taken"], "steps_taken", 0)


# ── Payload makers ──────────────────────────────────────────────


def make_chain_created_payload(
    *,
    chain_id: str,
    fault_id: str,
    fault_type: str,
    steps_count: int,
    strategies: list[str],
    tv: int = ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "chain_id": chain_id,
        "fault_id": fault_id,
        "fault_type": fault_type,
        "steps_count": steps_count,
        "strategies": strategies,
        "template_version": tv,
    }
    validate_chain_created(p)
    return p


def make_step_started_payload(
    *,
    chain_id: str,
    fault_id: str,
    strategy: str,
    order: int,
    step_index: int,
    tv: int = ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "chain_id": chain_id,
        "fault_id": fault_id,
        "strategy": strategy,
        "order": order,
        "step_index": step_index,
        "template_version": tv,
    }
    validate_step_started(p)
    return p


def make_step_failed_payload(
    *,
    chain_id: str,
    fault_id: str,
    strategy: str,
    order: int,
    reason: str = "step_failed",
    tv: int = ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "chain_id": chain_id,
        "fault_id": fault_id,
        "strategy": strategy,
        "order": order,
        "reason": reason,
        "template_version": tv,
    }
    validate_step_failed(p)
    return p


def make_step_succeeded_payload(
    *,
    chain_id: str,
    fault_id: str,
    strategy: str,
    order: int,
    confidence: float = 0.0,
    tv: int = ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "chain_id": chain_id,
        "fault_id": fault_id,
        "strategy": strategy,
        "order": order,
        "confidence": confidence,
        "template_version": tv,
    }
    validate_step_succeeded(p)
    return p


def make_strategy_switched_payload(
    *,
    chain_id: str,
    fault_id: str,
    from_strategy: str,
    to_strategy: str,
    reason: str = "step_failed_switching",
    tv: int = ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "chain_id": chain_id,
        "fault_id": fault_id,
        "from_strategy": from_strategy,
        "to_strategy": to_strategy,
        "reason": reason,
        "template_version": tv,
    }
    validate_strategy_switched(p)
    return p


def make_adaptive_recovery_completed_payload(
    *,
    chain_id: str,
    fault_id: str,
    outcome: str,
    steps_taken: int,
    tv: int = ADAPTIVE_RECOVERY_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "chain_id": chain_id,
        "fault_id": fault_id,
        "outcome": outcome,
        "steps_taken": steps_taken,
        "template_version": tv,
    }
    validate_adaptive_recovery_completed(p)
    return p
