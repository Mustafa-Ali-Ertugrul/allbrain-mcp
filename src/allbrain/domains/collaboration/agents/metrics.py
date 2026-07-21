from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExecutionMetrics:
    agent_id: str
    node_id: str
    workflow_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    success: bool = False
    error_type: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "node_id": self.node_id,
            "workflow_id": self.workflow_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "success": self.success,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "metadata": dict(self.metadata),
        }


class MetricsCollector:
    """Thread-safe collector for execution metrics."""

    def __init__(self) -> None:
        self._metrics: list[ExecutionMetrics] = []

    def record(self, metrics: ExecutionMetrics) -> None:
        self._metrics.append(metrics)

    def all(self) -> list[ExecutionMetrics]:
        return list(self._metrics)

    def by_agent(self, agent_id: str) -> list[ExecutionMetrics]:
        return [m for m in self._metrics if m.agent_id == agent_id]

    def by_workflow(self, workflow_id: str) -> list[ExecutionMetrics]:
        return [m for m in self._metrics if m.workflow_id == workflow_id]

    def aggregate(self, agent_id: str | None = None) -> dict[str, Any]:
        items = self.by_agent(agent_id) if agent_id else self._metrics
        if not items:
            return {
                "count": 0,
                "success_count": 0,
                "failure_count": 0,
                "total_cost": 0.0,
                "avg_duration_ms": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
        success = [m for m in items if m.success]
        failure = [m for m in items if not m.success]
        return {
            "count": len(items),
            "success_count": len(success),
            "failure_count": len(failure),
            "total_cost": sum(m.cost_usd for m in items),
            "avg_duration_ms": sum(m.duration_ms for m in items) / len(items),
            "total_input_tokens": sum(m.input_tokens for m in items),
            "total_output_tokens": sum(m.output_tokens for m in items),
        }

    def clear(self) -> None:
        self._metrics.clear()
