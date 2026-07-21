from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from allbrain.collaboration import CollaborationMetrics
from allbrain.domains.learning.evolution import LearningMetrics
from allbrain.domains.governance.governance import GovernanceMetrics
from allbrain.models.schemas import EventRead
from allbrain.observability.tracer import Tracer
from allbrain.domains.governance.reliability import ReliabilityMetrics
from allbrain.runtime_core import RuntimeCoreMetrics


class DashboardDataBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        spans = Tracer().build_spans(events)
        latencies = sorted(span.latency_ms or 0 for span in spans)
        cost_by_kind: dict[str, float] = defaultdict(float)
        failures = Counter()
        for span in spans:
            cost_by_kind[span.kind] += span.cost_usd
            if span.status == "error":
                failures[(span.kind, span.agent_id or "unknown")] += 1
        return {
            "latency_histogram": self._histogram(latencies),
            "latency_p95_ms": self._percentile(latencies, 0.95),
            "latency_p99_ms": self._percentile(latencies, 0.99),
            "cost_breakdown": dict(sorted(cost_by_kind.items())),
            "failure_heatmap": [
                {"kind": kind, "agent_id": agent_id, "count": count}
                for (kind, agent_id), count in sorted(failures.items())
            ],
            "reliability": ReliabilityMetrics().build(events),
            "collaboration": CollaborationMetrics().build(events),
            "learning": LearningMetrics().build(events),
            "governance": GovernanceMetrics().build(events),
            "runtime_core": RuntimeCoreMetrics().build(events),
        }

    def _histogram(self, values: list[int]) -> dict[str, int]:
        buckets = {"0-100": 0, "101-1000": 0, "1001-5000": 0, "5001+": 0}
        for value in values:
            if value <= 100:
                buckets["0-100"] += 1
            elif value <= 1000:
                buckets["101-1000"] += 1
            elif value <= 5000:
                buckets["1001-5000"] += 1
            else:
                buckets["5001+"] += 1
        return buckets

    def _percentile(self, values: list[int], percentile: float) -> int:
        if not values:
            return 0
        index = min(len(values) - 1, int((len(values) - 1) * percentile))
        return values[index]
