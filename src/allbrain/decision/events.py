from __future__ import annotations

from allbrain.decision.model import DECISION_TEMPLATE_VERSION

DECISION_KEYS: frozenset[str] = frozenset({"agent_id", "task_type", "score", "mode", "contributors", "backend_trace"})


def validate_decision(p: dict) -> None:
    m = DECISION_KEYS - set(p.keys())
    if m:
        raise ValueError("decision payload missing: " + str(m))
    for f in ("agent_id", "task_type", "mode"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    v = p.get("score")
    if not isinstance(v, (int, float)):
        raise ValueError("score must be numeric")


def make_decision_payload(
    *,
    agent_id: str,
    task_type: str,
    score: float,
    mode: str,
    contributors: dict[str, float] | None = None,
    backend_trace: tuple[str, ...] | None = None,
    tv: int = DECISION_TEMPLATE_VERSION,
) -> dict:
    if contributors is None:
        contributors = {}
    if backend_trace is None:
        backend_trace = ()
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "score": float(score),
        "mode": str(mode),
        "contributors": dict(contributors),
        "backend_trace": list(backend_trace),
        "template_version": int(tv),
    }
    validate_decision(p)
    return p
