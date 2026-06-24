from __future__ import annotations

import re
from typing import Iterable

from allbrain.capabilities.model import EXACT_MATCH, NO_MATCH, PARTIAL_MATCH


def _stable_capability_id(agent_id: str, event_ids: Iterable[str] | None = None) -> str:
    import hashlib
    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{agent_id}:{ek}".encode("utf-8")).digest()
    return f"capability-{d.hex()[:12]}"


def normalize_task_type(task_type: str) -> str:
    return re.sub(r"[^a-z0-9]", "", task_type.lower())


def match_kind(agent_capability: str, task_type: str) -> str:
    ac = normalize_task_type(agent_capability)
    tt = normalize_task_type(task_type)
    if ac == tt:
        return "exact"
    if ac and tt and (ac in tt or tt in ac):
        return "partial"
    return "none"


def match_score(
    *,
    agent_capabilities: list[tuple[str, float]],
    task_type: str,
) -> tuple[float, str]:
    if not agent_capabilities:
        return NO_MATCH, "none"
    scores: list[float] = []
    kinds: list[str] = []
    for cap_name, weight in agent_capabilities:
        mk = match_kind(cap_name, task_type)
        if mk == "exact":
            scores.append(EXACT_MATCH * weight)
            kinds.append("exact")
        elif mk == "partial":
            scores.append(PARTIAL_MATCH * weight)
            kinds.append("partial")
        else:
            scores.append(NO_MATCH * weight)
            kinds.append("none")
    if not scores:
        return NO_MATCH, "none"
    avg = sum(scores) / len(scores)
    if "exact" in kinds:
        return max(0.0, min(1.0, avg)), "exact"
    if "partial" in kinds:
        return max(0.0, min(1.0, avg)), "partial"
    return max(0.0, min(1.0, avg)), "none"