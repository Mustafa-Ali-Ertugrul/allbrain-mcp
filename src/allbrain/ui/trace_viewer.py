from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.observability import Tracer


class TraceViewer:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        spans = [span.to_dict() for span in Tracer().build_spans(events)]
        timeline = [
            {
                "id": span["span_id"],
                "parent_id": span["parent_span_id"],
                "kind": span["kind"],
                "label": f"{span['kind']}:{span.get('agent_id') or span.get('task_id') or span.get('workflow_id')}",
                "start_time": span["start_time"],
                "end_time": span["end_time"],
                "latency_ms": span["latency_ms"],
                "status": span["status"],
            }
            for span in sorted(spans, key=lambda item: (item["start_time"] or "", item["span_id"]))
        ]
        return {
            "rows": [
                {
                    "id": span["span_id"],
                    "parent_id": span["parent_span_id"],
                    "label": f"{span['kind']}:{span.get('agent_id') or span.get('task_id') or span.get('workflow_id')}",
                    "status": span["status"],
                    "latency_ms": span["latency_ms"],
                    "cost_usd": span["cost_usd"],
                }
                for span in spans
            ],
            "timeline": timeline,
            "cost_overlay": {"total_cost_usd": round(sum(float(span["cost_usd"]) for span in spans), 6)},
        }
