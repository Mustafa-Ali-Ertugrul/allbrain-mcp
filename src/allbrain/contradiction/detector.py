from __future__ import annotations

from allbrain.events import EventType
from allbrain.intent.models import Intent

SEVERITY_GOAL_DIVERGENCE = 50
SEVERITY_LIFECYCLE_INCOMPATIBLE_SAME_GOAL = 85
SEVERITY_LIFECYCLE_INCOMPATIBLE_SHARED = 70

CONTRADICTION_TEMPLATE_VERSION = 1

INCOMPATIBLE_LIFECYCLE: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({EventType.TASK_COMPLETED.value, EventType.TASK_BLOCKED.value}),
        frozenset({EventType.TASK_COMPLETED.value, EventType.FAILURE.value}),
    }
)


def _lifecycle_value(intent: Intent) -> str | None:
    sub_goal = intent.sub_goal
    if not sub_goal:
        return None
    return sub_goal


def _pair_signature(contradiction: dict) -> frozenset[str]:
    return frozenset(contradiction.get("evidence_intent_ids", []))


def dedup_contradictions(contradictions: list[dict]) -> list[dict]:
    """Drop duplicate contradictions over the same intent pair, keeping highest severity."""
    by_key: dict[frozenset[str], dict] = {}
    for contradiction in contradictions:
        key = _pair_signature(contradiction)
        if not key:
            continue
        existing = by_key.get(key)
        if existing is None or contradiction.get("severity_score", 0) > existing.get("severity_score", 0):
            by_key[key] = contradiction
    return list(by_key.values())


class ContradictionDetector:
    def detect(self, intents: list[Intent]) -> list[dict]:
        contradictions: list[dict] = []
        for index, a in enumerate(intents):
            for b in intents[index + 1 :]:
                if a.agent_id == b.agent_id:
                    continue
                shared_files = sorted(set(a.related_files) & set(b.related_files))
                same_goal = a.goal == b.goal
                lifecycle_pair = (
                    _lifecycle_value(a) or "",
                    _lifecycle_value(b) or "",
                )
                lifecycle_frozenset = frozenset(lifecycle_pair)
                if shared_files and not same_goal and not self._supportive_pair(a.goal, b.goal):
                    contradictions.append(
                        self._contradiction(a, b, shared_files, SEVERITY_GOAL_DIVERGENCE)
                    )
                elif same_goal and lifecycle_frozenset in INCOMPATIBLE_LIFECYCLE:
                    contradictions.append(
                        self._contradiction(a, b, shared_files, SEVERITY_LIFECYCLE_INCOMPATIBLE_SAME_GOAL)
                    )
                elif shared_files and lifecycle_frozenset in INCOMPATIBLE_LIFECYCLE:
                    contradictions.append(
                        self._contradiction(a, b, shared_files, SEVERITY_LIFECYCLE_INCOMPATIBLE_SHARED)
                    )
        return contradictions

    def _contradiction(self, a: Intent, b: Intent, related_files: list[str], severity_score: int) -> dict:
        return {
            "severity": self._severity_label(severity_score),
            "severity_score": severity_score,
            "agents": sorted([a.agent_id, b.agent_id]),
            "related_files": related_files,
            "a_goal": a.goal,
            "b_goal": b.goal,
            "evidence_intent_ids": [a.intent_id, b.intent_id],
        }

    def _severity_label(self, severity_score: int) -> str:
        if severity_score >= 90:
            return "fatal"
        if severity_score >= 75:
            return "critical"
        if severity_score >= 50:
            return "warning"
        return "info"

    def _supportive_pair(self, a_goal: str, b_goal: str) -> bool:
        a = a_goal.lower()
        b = b_goal.lower()
        supportive_terms = {"test", "tests", "doc", "docs", "documentation"}
        risky_terms = {"refactor", "fix", "cleanup", "migrate", "implement"}
        a_support = any(term in a for term in supportive_terms)
        b_support = any(term in b for term in supportive_terms)
        a_risky = any(term in a for term in risky_terms)
        b_risky = any(term in b for term in risky_terms)
        return (a_support and b_risky) or (b_support and a_risky)
