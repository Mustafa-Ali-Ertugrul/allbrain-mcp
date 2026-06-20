from __future__ import annotations

from typing import Any

from allbrain.metrics import AdvancedMetrics, AgentRanking
from allbrain.models.schemas import EventRead
from allbrain.observability import DashboardDataBuilder


class MetricsDashboard:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        dashboard = DashboardDataBuilder().build(events)
        return {
            "leaderboard": AgentRanking().leaderboard(events),
            "latency_cards": AdvancedMetrics().build(events)["agents"],
            "cost_heatmap": dashboard["cost_breakdown"],
            "failure_heatmap": dashboard["failure_heatmap"],
            "governance": dashboard["governance"],
            "runtime_core": dashboard["runtime_core"],
        }
