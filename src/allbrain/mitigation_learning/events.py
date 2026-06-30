from __future__ import annotations

from typing import Any

from allbrain.mitigation_learning.model import MITIGATION_LEARNING_TEMPLATE_VERSION

EVALUATED_KEYS: frozenset[str] = frozenset(
    {
        "learning_id",
        "fault_id",
        "fault_type",
        "signal_type",
        "strategy",
        "effectiveness_score",
        "success",
    }
)
OUTCOME_MEASURED_KEYS: frozenset[str] = frozenset(
    {
        "outcome_id",
        "fault_id",
        "plan_id",
        "strategy",
        "pre_risk",
        "post_risk",
        "risk_delta",
        "failure_prevented",
        "stability_delta",
    }
)
STRATEGY_UPDATED_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "signal_type",
        "strategy",
        "total_uses",
        "successes",
        "failures",
        "avg_effectiveness",
        "success_rate",
        "disabled",
    }
)
POLICY_IMPROVED_KEYS: frozenset[str] = frozenset(
    {
        "fault_type",
        "version",
        "created_at",
        "disabled_strategies",
        "strategy_preferences",
        "urgency_multipliers",
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


def _check_float_in_range(
    v: Any,
    label: str,
    lo: float = 0.0,
    hi: float = 1.0,
) -> float:
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


def validate_mitigation_evaluated(p: dict[str, Any]) -> None:
    _check_keys(p, EVALUATED_KEYS, "mitigation_evaluated")
    _check_str(p["learning_id"], "learning_id")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["signal_type"], "signal_type")
    _check_str(p["strategy"], "strategy")
    _check_float_in_range(p["effectiveness_score"], "effectiveness_score", -1.0, 1.0)
    if not isinstance(p.get("success"), bool):
        raise ValueError("success must be bool")


def validate_outcome_measured(p: dict[str, Any]) -> None:
    _check_keys(p, OUTCOME_MEASURED_KEYS, "outcome_measured")
    _check_str(p["outcome_id"], "outcome_id")
    _check_str(p["fault_id"], "fault_id")
    _check_str(p["plan_id"], "plan_id")
    _check_str(p["strategy"], "strategy")
    _check_float_in_range(p["pre_risk"], "pre_risk")
    _check_float_in_range(p["post_risk"], "post_risk")
    _check_float_in_range(p["risk_delta"], "risk_delta", -1.0, 1.0)
    if not isinstance(p.get("failure_prevented"), bool):
        raise ValueError("failure_prevented must be bool")
    _check_float_in_range(p["stability_delta"], "stability_delta")


def validate_strategy_updated(p: dict[str, Any]) -> None:
    _check_keys(p, STRATEGY_UPDATED_KEYS, "strategy_updated")
    _check_str(p["fault_type"], "fault_type")
    _check_str(p["signal_type"], "signal_type")
    _check_str(p["strategy"], "strategy")
    _check_int_ge(p["total_uses"], "total_uses", 0)
    _check_int_ge(p["successes"], "successes", 0)
    _check_int_ge(p["failures"], "failures", 0)
    _check_float_in_range(p["avg_effectiveness"], "avg_effectiveness", -1.0, 1.0)
    _check_float_in_range(p["success_rate"], "success_rate")
    if not isinstance(p.get("disabled"), bool):
        raise ValueError("disabled must be bool")


def validate_policy_improved(p: dict[str, Any]) -> None:
    _check_keys(p, POLICY_IMPROVED_KEYS, "policy_improved")
    _check_str(p["fault_type"], "fault_type")
    _check_int_ge(p["version"], "version", 1)
    if not isinstance(p.get("created_at"), (int, float)):
        raise ValueError("created_at must be numeric")
    if not isinstance(p.get("disabled_strategies"), (list, tuple)):
        raise ValueError("disabled_strategies must be list/tuple")
    if not isinstance(p.get("strategy_preferences"), dict):
        raise ValueError("strategy_preferences must be dict")
    if not isinstance(p.get("urgency_multipliers"), dict):
        raise ValueError("urgency_multipliers must be dict")


def make_outcome_measured_payload(
    *,
    outcome_id: str,
    fault_id: str,
    plan_id: str,
    strategy: str,
    pre_risk: float,
    post_risk: float,
    risk_delta: float,
    failure_prevented: bool,
    stability_delta: float,
    tv: int = MITIGATION_LEARNING_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "outcome_id": outcome_id,
        "fault_id": fault_id,
        "plan_id": plan_id,
        "strategy": strategy,
        "pre_risk": pre_risk,
        "post_risk": post_risk,
        "risk_delta": risk_delta,
        "failure_prevented": failure_prevented,
        "stability_delta": stability_delta,
        "template_version": tv,
    }
    validate_outcome_measured(p)
    return p


def make_mitigation_evaluated_payload(
    *,
    learning_id: str,
    fault_id: str,
    fault_type: str,
    signal_type: str,
    strategy: str,
    effectiveness_score: float,
    success: bool,
    tv: int = MITIGATION_LEARNING_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "learning_id": learning_id,
        "fault_id": fault_id,
        "fault_type": fault_type,
        "signal_type": signal_type,
        "strategy": strategy,
        "effectiveness_score": effectiveness_score,
        "success": success,
        "template_version": tv,
    }
    validate_mitigation_evaluated(p)
    return p


def make_strategy_updated_payload(
    *,
    fault_type: str,
    signal_type: str,
    strategy: str,
    total_uses: int,
    successes: int,
    failures: int,
    avg_effectiveness: float,
    success_rate: float,
    disabled: bool,
    tv: int = MITIGATION_LEARNING_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "signal_type": signal_type,
        "strategy": strategy,
        "total_uses": total_uses,
        "successes": successes,
        "failures": failures,
        "avg_effectiveness": avg_effectiveness,
        "success_rate": success_rate,
        "disabled": disabled,
        "template_version": tv,
    }
    validate_strategy_updated(p)
    return p


def make_policy_improved_payload(
    *,
    fault_type: str,
    version: int,
    created_at: float,
    disabled_strategies: list[str],
    strategy_preferences: dict[str, float],
    urgency_multipliers: dict[str, float],
    tv: int = MITIGATION_LEARNING_TEMPLATE_VERSION,
) -> dict[str, Any]:
    p: dict[str, Any] = {
        "fault_type": fault_type,
        "version": version,
        "created_at": created_at,
        "disabled_strategies": disabled_strategies,
        "strategy_preferences": strategy_preferences,
        "urgency_multipliers": urgency_multipliers,
        "template_version": tv,
    }
    validate_policy_improved(p)
    return p
