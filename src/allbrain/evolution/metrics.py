from __future__ import annotations

from collections import Counter
from typing import Any

from allbrain.evolution.organizational_learning import OrganizationalLearning
from allbrain.models.schemas import EventRead


class LearningMetrics:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        counts = Counter(event.type for event in events)
        learning = OrganizationalLearning().learn(events)
        recommendations = counts["recommendation_generated"]
        applied = counts["recommendation_applied"]
        rejected = counts["recommendation_rejected"]
        outcomes = applied + rejected
        return {
            "learning_confidence": learning["learning_confidence"],
            "recommendation_accuracy": round(applied / outcomes, 6) if outcomes else 0.0,
            "organizational_efficiency": _average_success(learning),
            "optimization_impact": applied - rejected,
            "policy_improvement_rate": round(
                counts["policy_update_approved"] / max(counts["policy_update_proposed"], 1), 6
            ),
            "team_effectiveness_trend": {
                pattern["team_name"]: pattern["success_rate"] for pattern in learning["team_patterns"]
            },
        }


def _average_success(learning: dict[str, Any]) -> float:
    rates: list[float] = []
    for key in ["team_patterns", "delegation_patterns", "consensus_patterns"]:
        rates.extend(float(pattern["success_rate"]) for pattern in learning[key])
    return round(sum(rates) / len(rates), 6) if rates else 0.0
