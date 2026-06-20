from __future__ import annotations

from allbrain.intent.models import Intent


INCOMPATIBLE_LIFECYCLE = {
    ("task_completed", "task_blocked"),
    ("task_blocked", "task_completed"),
    ("task_completed", "failure"),
    ("failure", "task_completed"),
}


class ContradictionDetector:
    def detect(self, intents: list[Intent]) -> list[dict]:
        contradictions: list[dict] = []
        for index, a in enumerate(intents):
            for b in intents[index + 1 :]:
                if a.agent_id == b.agent_id:
                    continue
                shared_files = sorted(set(a.related_files) & set(b.related_files))
                same_goal = a.goal == b.goal
                lifecycle_pair = (a.sub_goal or "", b.sub_goal or "")
                if shared_files and not same_goal and not self._supportive_pair(a.goal, b.goal):
                    contradictions.append(self._contradiction(a, b, shared_files, 50))
                elif same_goal and lifecycle_pair in INCOMPATIBLE_LIFECYCLE:
                    contradictions.append(self._contradiction(a, b, shared_files, 85))
                elif shared_files and lifecycle_pair in INCOMPATIBLE_LIFECYCLE:
                    contradictions.append(self._contradiction(a, b, shared_files, 70))
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
