from __future__ import annotations

from allbrain.capabilities.model import CAPABILITY_TEMPLATE_VERSION


REG_KEYS: frozenset[str] = frozenset({"agent_id", "capability", "weight"})
CLASSIFIED_KEYS: frozenset[str] = frozenset({"task_id", "task_type"})
MATCHED_KEYS: frozenset[str] = frozenset({"agent_id", "task_type", "match_score", "match_kind"})


def validate_registered(payload: dict) -> None:
    m = REG_KEYS - set(payload.keys())
    if m:
        raise ValueError("registered missing: " + str(m))
    for f in ("agent_id", "capability"):
        v = payload.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    w = payload.get("weight")
    if not isinstance(w, (int, float)) or not 0.0 <= float(w) <= 1.0:
        raise ValueError("weight must be in [0,1]")


def validate_classified(payload: dict) -> None:
    m = CLASSIFIED_KEYS - set(payload.keys())
    if m:
        raise ValueError("classified missing: " + str(m))
    for f in ("task_id", "task_type"):
        v = payload.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")


def validate_matched(payload: dict) -> None:
    m = MATCHED_KEYS - set(payload.keys())
    if m:
        raise ValueError("matched missing: " + str(m))
    for f in ("agent_id", "task_type", "match_kind"):
        v = payload.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    s = payload.get("match_score")
    if not isinstance(s, (int, float)) or not 0.0 <= float(s) <= 1.0:
        raise ValueError("match_score must be in [0,1]")


def make_registered_payload(*, agent_id: str, capability: str, weight: float,
                            tv: int = CAPABILITY_TEMPLATE_VERSION) -> dict:
    p = {"agent_id": str(agent_id), "capability": str(capability),
         "weight": float(weight), "template_version": int(tv)}
    validate_registered(p)
    return p


def make_classified_payload(*, task_id: str, task_type: str,
                            tv: int = CAPABILITY_TEMPLATE_VERSION) -> dict:
    p = {"task_id": str(task_id), "task_type": str(task_type),
         "template_version": int(tv)}
    validate_classified(p)
    return p


def make_matched_payload(*, agent_id: str, task_type: str, match_score: float,
                         match_kind: str, tv: int = CAPABILITY_TEMPLATE_VERSION) -> dict:
    p = {"agent_id": str(agent_id), "task_type": str(task_type),
         "match_score": float(match_score), "match_kind": str(match_kind),
         "template_version": int(tv)}
    validate_matched(p)
    return p