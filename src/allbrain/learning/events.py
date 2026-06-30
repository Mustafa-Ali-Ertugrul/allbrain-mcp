from __future__ import annotations

from allbrain.learning.model import LEARNING_TEMPLATE_VERSION

OBSERVED_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "success", "runtime_score", "selection_score"}
)
LEARNED_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "old_score", "new_score", "delta"}
)
DECAYED_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "old_score", "new_score"}
)


def validate_observed(p: dict) -> None:
    m = OBSERVED_KEYS - set(p.keys())
    if m:
        raise ValueError("observed missing: " + str(m))
    for f in ("agent_id", "task_type"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    if not isinstance(p.get("success"), bool):
        raise ValueError("success must be bool")
    for f in ("runtime_score", "selection_score"):
        v = p.get(f)
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            raise ValueError(f + " must be in [0,1]")


def validate_learned(p: dict) -> None:
    m = LEARNED_KEYS - set(p.keys())
    if m:
        raise ValueError("learned missing: " + str(m))
    for f in ("agent_id", "task_type"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("old_score", "new_score", "delta"):
        v = p.get(f)
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            raise ValueError(f + " must be in [0,1]")


def validate_decayed(p: dict) -> None:
    m = DECAYED_KEYS - set(p.keys())
    if m:
        raise ValueError("decayed missing: " + str(m))
    for f in ("agent_id", "task_type"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("old_score", "new_score"):
        v = p.get(f)
        if not isinstance(v, (int, float)) or not 0.0 <= float(v) <= 1.0:
            raise ValueError(f + " must be in [0,1]")


def make_observed_payload(
    *, agent_id: str, task_type: str, success: bool,
    runtime_score: float, selection_score: float,
    tv: int = LEARNING_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id), "task_type": str(task_type),
        "success": bool(success), "runtime_score": float(runtime_score),
        "selection_score": float(selection_score), "template_version": int(tv),
    }
    validate_observed(p)
    return p


def make_learned_payload(
    *, agent_id: str, task_type: str, old_score: float,
    new_score: float, delta: float,
    tv: int = LEARNING_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id), "task_type": str(task_type),
        "old_score": float(old_score), "new_score": float(new_score),
        "delta": float(delta), "template_version": int(tv),
    }
    validate_learned(p)
    return p


def make_decayed_payload(
    *, agent_id: str, task_type: str, old_score: float, new_score: float,
    tv: int = LEARNING_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id), "task_type": str(task_type),
        "old_score": float(old_score), "new_score": float(new_score),
        "template_version": int(tv),
    }
    validate_decayed(p)
    return p
