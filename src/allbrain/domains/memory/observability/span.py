from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Span:
    span_id: str
    trace_id: str
    workflow_id: str | None
    task_id: str | None
    node_id: str | None
    agent_id: str | None
    kind: str
    start_time: datetime
    end_time: datetime | None = None
    latency_ms: int | None = None
    cost_usd: float = 0.0
    status: str = "ok"
    parent_span_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "workflow_id": self.workflow_id,
            "task_id": self.task_id,
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "kind": self.kind,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "status": self.status,
            "parent_span_id": self.parent_span_id,
            "attributes": self.attributes,
        }
