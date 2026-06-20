from __future__ import annotations

import time
from typing import Any

from allbrain.agents.adapter import AgentAdapter, ExecutionContext
from allbrain.workflow.models import SubtaskResult


class MockAdapter(AgentAdapter):
    """Mock adapter for testing without real LLM calls."""

    def __init__(
        self,
        definition,
        *,
        response_delay_ms: int = 1,
        fail_on: set[str] | None = None,
        output_template: str | None = None,
    ) -> None:
        super().__init__(definition)
        self.response_delay_ms = response_delay_ms
        self.fail_on = fail_on or set()
        self.output_template = output_template
        self.call_count = 0

    def execute(
        self,
        *,
        task: dict[str, Any],
        context: ExecutionContext,
    ) -> SubtaskResult:
        self.call_count += 1
        time.sleep(self.response_delay_ms / 1000.0)

        goal = task.get("goal", "")
        if context.node_id in self.fail_on or goal in self.fail_on:
            self._update_health(success=False, error="mock failure")
            return SubtaskResult(
                node_id=context.node_id,
                agent_id=self.definition.id,
                output="",
                artifacts=[],
                metadata={"error": "mock failure", "cost_usd": 0.0},
            )

        template = self.output_template or f"Mock output for: {goal}"
        output = template
        self._update_health(success=True)
        return SubtaskResult(
            node_id=context.node_id,
            agent_id=self.definition.id,
            output=output,
            artifacts=[],
            metadata={
                "cost_usd": 0.0,
                "mock": True,
                "kind": task.get("kind", "implementation"),
            },
        )

    def estimate_cost(self, task: dict[str, Any]) -> float:
        return self.definition.cost.avg_cost_per_call
