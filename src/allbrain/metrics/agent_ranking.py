from __future__ import annotations

from typing import Any

from allbrain.metrics.advanced_metrics import AdvancedMetrics
from allbrain.models.schemas import EventRead
from allbrain.orchestrator.metrics import AgentPerformanceReducer


class AgentRanking:
    def leaderboard(self, events: list[EventRead]) -> list[dict[str, Any]]:
        performance = AgentPerformanceReducer().reduce(events)
        advanced = AdvancedMetrics().build(events)["agents"]
        rows: list[dict[str, Any]] = []
        for agent_id in sorted(set(performance) | set(advanced)):
            perf = performance.get(agent_id, {})
            adv = advanced.get(agent_id, {})
            success_rate = float(perf.get("success_rate", 0.0) or 0.0)
            confidence = float(perf.get("confidence", 0.0) or 0.0)
            latency_score = _latency_score(int(adv.get("p95_latency_ms", 0) or 0))
            cost_score = _cost_score(float(adv.get("cost_per_success", 0.0) or 0.0))
            efficiency = round(
                success_rate * 0.45 + confidence * 0.25 + latency_score * 0.15 + cost_score * 0.15,
                6,
            )
            rows.append(
                {
                    "agent_id": agent_id,
                    "efficiency_score": efficiency,
                    "success_rate": success_rate,
                    "confidence": confidence,
                    "p95_latency_ms": adv.get("p95_latency_ms", 0),
                    "cost_per_success": adv.get("cost_per_success", 0.0),
                }
            )
        rows.sort(key=lambda item: (-item["efficiency_score"], item["agent_id"]))
        return rows


def _latency_score(p95_latency_ms: int) -> float:
    return max(0.0, min(1.0, 1 - p95_latency_ms / 10_000))


def _cost_score(cost_per_success: float) -> float:
    return max(0.0, min(1.0, 1 - cost_per_success))
