from __future__ import annotations

from typing import Any

from uuid6 import uuid7


class RecommendationEngine:
    def generate(self, *, kind: str, subject: str, confidence: float, evidence: list[str], source_metrics: dict[str, Any]) -> dict[str, Any]:
        return {
            "recommendation_id": str(uuid7()),
            "kind": kind,
            "subject": subject,
            "confidence": round(max(0.0, min(confidence, 1.0)), 6),
            "supporting_evidence": list(evidence),
            "source_metrics": dict(source_metrics),
        }
