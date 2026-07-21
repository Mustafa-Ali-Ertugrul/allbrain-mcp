from __future__ import annotations

from typing import Any

from allbrain.domains.learning.evolution.organizational_learning import OrganizationalLearning
from allbrain.domains.learning.evolution.recommendation_engine import RecommendationEngine
from allbrain.models.schemas import EventRead


class LearningManager:
    def run_cycle(self, events: list[EventRead]) -> dict[str, Any]:
        learning = OrganizationalLearning().learn(events)
        recommendations: list[dict[str, Any]] = []
        engine = RecommendationEngine()
        for pattern in learning["team_patterns"]:
            recommendations.append(
                engine.generate(
                    kind="team",
                    subject=pattern["team_name"],
                    confidence=pattern["confidence"],
                    evidence=pattern["evidence_event_ids"],
                    source_metrics={"success_rate": pattern["success_rate"], "sample_size": pattern["sample_size"]},
                )
            )
        for pattern in learning["delegation_patterns"]:
            recommendations.append(
                engine.generate(
                    kind="delegation",
                    subject=f"{pattern['from_agent']}->{pattern['to_agent']}",
                    confidence=pattern["confidence"],
                    evidence=pattern["evidence_event_ids"],
                    source_metrics={"success_rate": pattern["success_rate"], "sample_size": pattern["sample_size"]},
                )
            )
        return {"learning": learning, "recommendations": recommendations}
