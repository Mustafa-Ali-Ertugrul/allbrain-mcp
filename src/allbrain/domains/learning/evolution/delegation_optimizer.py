from __future__ import annotations

from collections import defaultdict
from typing import Any

from allbrain.models.schemas import EventRead


class DelegationOptimizer:
    def optimize(self, events: list[EventRead]) -> list[dict[str, Any]]:
        created: dict[str, dict[str, Any]] = {}
        outcomes: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "success": 0, "evidence_event_ids": []}
        )
        for event in events:
            delegation_id = event.payload.get("delegation_id")
            if not isinstance(delegation_id, str):
                continue
            if event.type == "delegation_created":
                created[delegation_id] = dict(event.payload)
            elif event.type in {"delegation_completed", "delegation_failed"} and delegation_id in created:
                source = str(created[delegation_id].get("from_agent"))
                target = str(created[delegation_id].get("to_agent"))
                bucket = outcomes[(source, target)]
                bucket["total"] += 1
                bucket["success"] += 1 if event.type == "delegation_completed" else 0
                bucket["evidence_event_ids"].append(event.id)
        return [
            {
                "from_agent": source,
                "to_agent": target,
                "success_rate": round(data["success"] / data["total"], 6) if data["total"] else 0.0,
                "sample_size": data["total"],
                "confidence": round(min(1.0, data["total"] / 10), 6),
                "evidence_event_ids": data["evidence_event_ids"],
            }
            for (source, target), data in sorted(outcomes.items())
        ]
