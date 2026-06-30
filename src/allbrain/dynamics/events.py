from __future__ import annotations

from allbrain.dynamics.model import DYNAMICS_TEMPLATE_VERSION

DRIFT_KEYS: frozenset[str] = frozenset({"agent_id", "task_type", "drift_score", "drift_level", "ema_short", "ema_long"})

TREND_KEYS: frozenset[str] = frozenset({"agent_id", "task_type", "slope", "label", "momentum", "consecutive_count"})

FORECAST_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "horizon", "predicted_capability", "confidence", "current_capability", "delta"}
)


def validate_drift(p: dict) -> None:
    m = DRIFT_KEYS - set(p.keys())
    if m:
        raise ValueError("drift payload missing: " + str(m))
    for f in ("agent_id", "task_type"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("drift_score", "ema_short", "ema_long"):
        v = p.get(f)
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            raise ValueError(f + " must be in [0,1]")
    if p["drift_level"] not in ("low", "medium", "high"):
        raise ValueError("drift_level must be low|medium|high")


def validate_trend(p: dict) -> None:
    m = TREND_KEYS - set(p.keys())
    if m:
        raise ValueError("trend payload missing: " + str(m))
    for f in ("agent_id", "task_type"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("slope", "momentum"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")
    if p["label"] not in ("stable", "improving", "degrading", "unstable"):
        raise ValueError("label must be stable|improving|degrading|unstable")
    v = p.get("consecutive_count")
    if not isinstance(v, int) or v < 0:
        raise ValueError("consecutive_count must be non-negative int")


def validate_forecast(p: dict) -> None:
    m = FORECAST_KEYS - set(p.keys())
    if m:
        raise ValueError("forecast payload missing: " + str(m))
    for f in ("agent_id", "task_type"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("predicted_capability", "confidence", "current_capability"):
        v = p.get(f)
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            raise ValueError(f + " must be in [0,1]")
    v = p.get("horizon")
    if not isinstance(v, int):
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise ValueError("horizon must be int")


def make_drift_payload(
    *,
    agent_id: str,
    task_type: str,
    drift_score: float,
    drift_level: str,
    ema_short: float,
    ema_long: float,
    tv: int = DYNAMICS_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "drift_score": float(drift_score),
        "drift_level": str(drift_level),
        "ema_short": float(ema_short),
        "ema_long": float(ema_long),
        "template_version": int(tv),
    }
    validate_drift(p)
    return p


def make_trend_payload(
    *,
    agent_id: str,
    task_type: str,
    slope: float,
    label: str,
    momentum: float,
    consecutive_count: int,
    tv: int = DYNAMICS_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "slope": float(slope),
        "label": str(label),
        "momentum": float(momentum),
        "consecutive_count": int(consecutive_count),
        "template_version": int(tv),
    }
    validate_trend(p)
    return p


def make_forecast_payload(
    *,
    agent_id: str,
    task_type: str,
    horizon: int,
    predicted_capability: float,
    confidence: float,
    current_capability: float,
    delta: float,
    tv: int = DYNAMICS_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "horizon": int(horizon),
        "predicted_capability": float(predicted_capability),
        "confidence": float(confidence),
        "current_capability": float(current_capability),
        "delta": float(delta),
        "template_version": int(tv),
    }
    validate_forecast(p)
    return p
