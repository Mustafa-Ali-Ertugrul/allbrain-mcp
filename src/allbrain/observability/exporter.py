from __future__ import annotations

from allbrain.observability.span import Span


class SpanExporter:
    def to_json(self, spans: list[Span]) -> list[dict[str, object]]:
        return [span.to_dict() for span in spans]

    def to_otel(self, spans: list[Span]) -> dict[str, object]:
        return {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": span.trace_id,
                                    "spanId": span.span_id,
                                    "parentSpanId": span.parent_span_id,
                                    "name": span.kind,
                                    "startTimeUnixNano": _unix_nano(span.start_time),
                                    "endTimeUnixNano": _unix_nano(span.end_time or span.start_time),
                                    "status": {"code": "ERROR" if span.status == "error" else "OK"},
                                    "attributes": _attributes(span),
                                }
                                for span in spans
                            ]
                        }
                    ]
                }
            ]
        }

    def to_prometheus(self, spans: list[Span]) -> str:
        lines = [
            "# HELP allbrain_span_latency_ms Event-derived span latency.",
            "# TYPE allbrain_span_latency_ms gauge",
            "# HELP allbrain_span_cost_usd Event-derived span cost.",
            "# TYPE allbrain_span_cost_usd gauge",
        ]
        for span in spans:
            labels = f'kind="{span.kind}",status="{span.status}"'
            lines.append(f"allbrain_span_latency_ms{{{labels}}} {span.latency_ms or 0}")
            lines.append(f"allbrain_span_cost_usd{{{labels}}} {span.cost_usd}")
        return "\n".join(lines)


def _unix_nano(value) -> int:
    return int(value.timestamp() * 1_000_000_000)


def _attributes(span: Span) -> list[dict[str, object]]:
    base = {
        "workflow_id": span.workflow_id,
        "task_id": span.task_id,
        "node_id": span.node_id,
        "agent_id": span.agent_id,
        "latency_ms": span.latency_ms,
        "cost_usd": span.cost_usd,
    } | span.attributes
    return [{"key": key, "value": {"stringValue": str(value)}} for key, value in base.items() if value is not None]
