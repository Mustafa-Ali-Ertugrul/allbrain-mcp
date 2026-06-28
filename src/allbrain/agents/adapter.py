from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from allbrain.agents.definition import AgentDefinition
from allbrain.workflow.models import SubtaskResult


class AgentStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class AgentHealth:
    status: AgentStatus = AgentStatus.UNKNOWN
    last_check_at: datetime | None = None
    error_message: str | None = None
    consecutive_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "last_check_at": self.last_check_at.isoformat() if self.last_check_at else None,
            "error_message": self.error_message,
            "consecutive_failures": self.consecutive_failures,
        }

    @property
    def is_healthy(self) -> bool:
        return self.status in {AgentStatus.HEALTHY, AgentStatus.DEGRADED}


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_base: float = 2.0
    max_delay_seconds: float = 60.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "backoff_base": self.backoff_base,
            "max_delay_seconds": self.max_delay_seconds,
        }


@dataclass
class ExecutionContext:
    workflow_id: str
    node_id: str
    task_id: str
    parent_results: dict[str, SubtaskResult] = field(default_factory=dict)
    snapshot_state: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 120.0
    max_tokens: int | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "task_id": self.task_id,
            "parent_results": {
                nid: r.to_dict() for nid, r in self.parent_results.items()
            },
            "snapshot_state": dict(self.snapshot_state),
            "timeout_seconds": self.timeout_seconds,
            "max_tokens": self.max_tokens,
            "retry_policy": self.retry_policy.to_dict(),
            "metadata": dict(self.metadata),
        }


class AgentAdapter(ABC):
    def __init__(self, definition: AgentDefinition) -> None:
        self.definition = definition
        self._health = AgentHealth(status=AgentStatus.UNKNOWN)

    @abstractmethod
    def execute(
        self,
        *,
        task: dict[str, Any],
        context: ExecutionContext,
    ) -> SubtaskResult:
        """Execute a subtask and return the result."""

    @abstractmethod
    def estimate_cost(self, task: dict[str, Any]) -> float:
        """Estimate cost before execution."""

    def health_check(self) -> AgentHealth:
        """Default implementation returns cached health."""
        return self._health

    def _update_health(self, success: bool, error: str | None = None) -> None:
        from datetime import datetime, timezone
        if success:
            self._health = AgentHealth(
                status=AgentStatus.HEALTHY,
                last_check_at=datetime.now(timezone.utc),
                consecutive_failures=0,
            )
        else:
            failures = self._health.consecutive_failures + 1
            status = AgentStatus.UNHEALTHY if failures >= 5 else AgentStatus.DEGRADED
            self._health = AgentHealth(
                status=status,
                last_check_at=datetime.now(timezone.utc),
                error_message=error,
                consecutive_failures=failures,
            )

    @property
    def agent_id(self) -> str:
        return self.definition.id
