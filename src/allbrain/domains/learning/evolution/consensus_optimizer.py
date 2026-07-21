from __future__ import annotations

from collections import defaultdict
from typing import Any

from allbrain.models.schemas import EventRead


class ConsensusOptimizer:
    def optimize(self, events: list[EventRead]) -> list[dict[str, Any]]:
        votes: dict[str, int] = defaultdict(int)
        results: dict[str, dict[str, Any]] = defaultdict(lambda: {"total": 0, "success": 0, "evidence_event_ids": []})
        for event in events:
            consensus_id = event.payload.get("consensus_id")
            if isinstance(consensus_id, str) and event.type == "vote_cast":
                votes[consensus_id] += 1
            if isinstance(consensus_id, str) and event.type in {"consensus_reached", "consensus_failed"}:
                mode = str(event.payload.get("mode") or ("unanimous" if votes[consensus_id] > 2 else "majority"))
                bucket = results[mode]
                bucket["total"] += 1
                bucket["success"] += 1 if event.type == "consensus_reached" else 0
                bucket["evidence_event_ids"].append(event.id)
        return [
            {
                "mode": mode,
                "success_rate": round(data["success"] / data["total"], 6) if data["total"] else 0.0,
                "sample_size": data["total"],
                "confidence": round(min(1.0, data["total"] / 10), 6),
                "evidence_event_ids": data["evidence_event_ids"],
            }
            for mode, data in sorted(results.items())
        ]
