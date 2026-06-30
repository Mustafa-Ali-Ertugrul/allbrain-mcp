from __future__ import annotations

from collections import defaultdict
from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.orchestrator.metrics import AgentPerformanceReducer


class AdvancedMetrics:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        latencies: dict[str, list[int]] = defaultdict(list)
        costs: dict[str, float] = defaultdict(float)
        for event in events:
            agent_id = event.payload.get("agent_id") or event.agent_id
            if not isinstance(agent_id, str) or not agent_id:
                continue
            duration = event.payload.get("duration_ms")
            if isinstance(duration, int | float):
                latencies[agent_id].append(int(duration))
            costs[agent_id] += float(event.payload.get("cost_usd", 0.0) or 0.0)
        performance = AgentPerformanceReducer().reduce(events)
        return {
            "agents": {
                agent_id: {
                    "p95_latency_ms": _percentile(values, 0.95),
                    "p99_latency_ms": _percentile(values, 0.99),
                    "cost_usd": round(costs[agent_id], 6),
                    "cost_per_success": _cost_per_success(costs[agent_id], performance.get(agent_id, {})),
                    "success_rate": performance.get(agent_id, {}).get("success_rate", 0.0),
                    "failure_rate": performance.get(agent_id, {}).get("failure_rate", 0.0),
                }
                for agent_id, values in sorted(latencies.items())
            },
            "system": {
                "total_cost_usd": round(sum(costs.values()), 6),
                "execution_events": sum(
                    1
                    for event in events
                    if event.type
                    in {
                        EventType.AGENT_EXECUTION_COMPLETED.value,
                        EventType.AGENT_EXECUTION_FAILED.value,
                    }
                ),
            },
        }


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    index = min(len(values) - 1, int((len(values) - 1) * percentile))
    return values[index]


def _cost_per_success(cost: float, metrics: dict[str, Any]) -> float:
    successes = int(metrics.get("success_count", 0) or 0)
    if successes == 0:
        return 0.0
    return round(cost / successes, 6)
