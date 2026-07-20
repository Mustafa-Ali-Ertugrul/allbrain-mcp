from __future__ import annotations

from allbrain.domains.analysis.attribution.model import ATTRIBUTION_TEMPLATE_VERSION

CREDIT_KEYS: frozenset[str] = frozenset({"decision_id", "signal", "contribution", "confidence"})

UPDATE_KEYS: frozenset[str] = frozenset({"signal", "ema_reward", "count"})

IMPORTANCE_KEYS: frozenset[str] = frozenset({"signal", "delta_importance", "direction"})


def validate_credit(p: dict) -> None:
    m = CREDIT_KEYS - set(p.keys())
    if m:
        raise ValueError("credit payload missing: " + str(m))
    if not isinstance(p.get("decision_id"), str) or not p["decision_id"]:
        raise ValueError("decision_id missing")
    for f in ("contribution", "confidence"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")


def validate_attribution_update(p: dict) -> None:
    m = UPDATE_KEYS - set(p.keys())
    if m:
        raise ValueError("attribution_update missing: " + str(m))
    for f in ("ema_reward",):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")


def validate_importance(p: dict) -> None:
    m = IMPORTANCE_KEYS - set(p.keys())
    if m:
        raise ValueError("importance payload missing: " + str(m))
    v = p.get("delta_importance")
    if not isinstance(v, (int, float)):
        raise ValueError("delta_importance must be numeric")


def make_credit_payload(
    *,
    decision_id: str,
    signal: str,
    contribution: float,
    confidence: float,
    tv: int = ATTRIBUTION_TEMPLATE_VERSION,
) -> dict:
    p = {
        "decision_id": decision_id,
        "signal": signal,
        "contribution": float(contribution),
        "confidence": float(confidence),
        "template_version": tv,
    }
    validate_credit(p)
    return p


def make_attribution_update_payload(
    *,
    signal: str,
    ema_reward: float,
    count: int,
    tv: int = ATTRIBUTION_TEMPLATE_VERSION,
) -> dict:
    p = {"signal": signal, "ema_reward": float(ema_reward), "count": int(count), "template_version": tv}
    validate_attribution_update(p)
    return p


def make_importance_payload(
    *,
    signal: str,
    delta_importance: float,
    direction: str,
    tv: int = ATTRIBUTION_TEMPLATE_VERSION,
) -> dict:
    p = {"signal": signal, "delta_importance": float(delta_importance), "direction": direction, "template_version": tv}
    validate_importance(p)
    return p
