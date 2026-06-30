from __future__ import annotations

from allbrain.routing.model import ROUTING_TEMPLATE_VERSION

REQ_KEYS = frozenset({"task_id", "task_type", "context_key"})
SCORED_KEYS = frozenset({"agent_id", "task_type", "selection_score", "reputation", "runtime_score", "calibrated_trust"})
SELECTED_KEYS = frozenset({"task_id", "task_type", "agent_id", "selection_score"})


def validate_req(payload: dict) -> None:
    m = REQ_KEYS - set(payload.keys())
    if m:
        raise ValueError("req missing: " + str(m))
    for f in ("task_id", "task_type", "context_key"):
        v = payload.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")


def validate_scored(payload: dict) -> None:
    m = SCORED_KEYS - set(payload.keys())
    if m:
        raise ValueError("scored missing: " + str(m))
    if not isinstance(payload.get("agent_id"), str) or not payload["agent_id"]:
        raise ValueError("agent_id must be non-empty string")
    for f in ("selection_score", "reputation", "runtime_score", "calibrated_trust"):
        v = payload.get(f)
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            raise ValueError(f + " must be in [0,1], got " + str(v))


def validate_selected(payload: dict) -> None:
    m = SELECTED_KEYS - set(payload.keys())
    if m:
        raise ValueError("selected missing: " + str(m))
    for f in ("task_id", "task_type", "agent_id"):
        v = payload.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    s = payload.get("selection_score")
    if not isinstance(s, (int, float)) or not 0.0 <= float(s) <= 1.0:
        raise ValueError("selection_score must be in [0,1]")


def make_req_payload(*, task_id: str, task_type: str, context_key: str, tv: int = ROUTING_TEMPLATE_VERSION) -> dict:
    p = {
        "task_id": str(task_id),
        "task_type": str(task_type),
        "context_key": str(context_key),
        "template_version": int(tv),
    }
    validate_req(p)
    return p


def make_scored_payload(
    *,
    agent_id: str,
    task_type: str,
    selection_score: float,
    reputation: float,
    runtime_score: float,
    calibrated_trust: float,
    rank: int = 0,
    tv: int = ROUTING_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "selection_score": float(selection_score),
        "reputation": float(reputation),
        "runtime_score": float(runtime_score),
        "calibrated_trust": float(calibrated_trust),
        "rank": int(rank),
        "template_version": int(tv),
    }
    validate_scored(p)
    return p


def make_selected_payload(
    *, task_id: str, task_type: str, agent_id: str, selection_score: float, tv: int = ROUTING_TEMPLATE_VERSION
) -> dict:
    p = {
        "task_id": str(task_id),
        "task_type": str(task_type),
        "agent_id": str(agent_id),
        "selection_score": float(selection_score),
        "template_version": int(tv),
    }
    validate_selected(p)
    return p
