from __future__ import annotations

from typing import Any

from uuid6 import uuid7


class PolicyFeedbackLoop:
    def propose_update(self, recommendation: dict[str, Any]) -> dict[str, Any]:
        return {
            "policy_update_id": str(uuid7()),
            "recommendation_id": recommendation.get("recommendation_id"),
            "status": "proposed",
            "explanation": f"Policy update proposed from {recommendation.get('kind')} recommendation",
            "source_metrics": recommendation.get("source_metrics", {}),
            "supporting_evidence": recommendation.get("supporting_evidence", []),
        }
