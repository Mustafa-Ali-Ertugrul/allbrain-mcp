from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from allbrain.agents.adapter import ExecutionContext, RetryPolicy
from allbrain.agents.learner import CapabilityLearner
from allbrain.agents.metrics import ExecutionMetrics, MetricsCollector
from allbrain.agents.registry import AgentRegistry
from allbrain.agents.safety import SafetyWrapper
from allbrain.workflow.models import SubtaskResult, TaskGraph
from allbrain.workflow.scheduler import SubtaskAssignment

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Bridges the workflow engine to agent adapters with safety, metrics, and learning."""

    def __init__(
        self,
        registry: AgentRegistry,
        *,
        metrics_collector: MetricsCollector | None = None,
        learner: CapabilityLearner | None = None,
        default_retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.metrics = metrics_collector or MetricsCollector()
        self.learner = learner or CapabilityLearner()
        self.default_retry_policy = default_retry_policy or RetryPolicy()

    def get_safety_wrapper(self, agent_id: str) -> SafetyWrapper:
        adapter = self.registry.get_adapter(agent_id)
        return SafetyWrapper(adapter=adapter)

    def _build_context(
        self,
        *,
        assignment: SubtaskAssignment,
        graph: TaskGraph,
        parent_results: dict[str, SubtaskResult] | None,
        timeout_seconds: float,
        metadata: dict[str, Any] | None,
    ) -> tuple[ExecutionContext, dict[str, Any]]:
        node = graph.nodes.get(assignment.node_id)
        if node is None:
            raise KeyError(f"Node '{assignment.node_id}' not found in graph")
        context = ExecutionContext(
            workflow_id=graph.root_task_id or "unknown",
            node_id=assignment.node_id,
            task_id=node.task_id,
            parent_results=parent_results or {},
            timeout_seconds=timeout_seconds,
            retry_policy=self.default_retry_policy,
            metadata=metadata or {},
        )
        task = {
            "task_id": node.task_id,
            "goal": node.goal,
            "kind": node.kind,
            "priority": node.priority,
            "domain": "software",
        }
        return context, task

    def _record_success(
        self,
        *,
        agent_id: str,
        node_id: str,
        workflow_id: str,
        task: dict[str, Any],
        start: datetime,
        result: SubtaskResult,
    ) -> None:
        completed = datetime.now(UTC)
        duration_ms = int((completed - start).total_seconds() * 1000)
        metrics = ExecutionMetrics(
            agent_id=agent_id,
            node_id=node_id,
            workflow_id=workflow_id,
            started_at=start,
            completed_at=completed,
            duration_ms=duration_ms,
            input_tokens=len(str(task.get("goal") or "")) // 4,
            output_tokens=len(result.output or "") // 4,
            cost_usd=float((result.metadata or {}).get("cost_usd", 0.0)),
            success=True,
        )
        self.metrics.record(metrics)
        self.learner.observe(agent_id=agent_id, task=task, metrics=metrics)

    def _record_failure(
        self,
        *,
        agent_id: str,
        node_id: str,
        workflow_id: str,
        task: dict[str, Any],
        start: datetime,
        error_type: str,
        error_message: str,
    ) -> None:
        completed = datetime.now(UTC)
        duration_ms = int((completed - start).total_seconds() * 1000)
        metrics = ExecutionMetrics(
            agent_id=agent_id,
            node_id=node_id,
            workflow_id=workflow_id,
            started_at=start,
            completed_at=completed,
            duration_ms=duration_ms,
            success=False,
            error_type=error_type,
            error_message=error_message,
        )
        self.metrics.record(metrics)
        self.learner.observe(agent_id=agent_id, task=task, metrics=metrics)

    async def execute_subtask(
        self,
        *,
        assignment: SubtaskAssignment,
        graph: TaskGraph,
        parent_results: dict[str, SubtaskResult] | None = None,
        timeout_seconds: float = 120.0,
        metadata: dict[str, Any] | None = None,
    ) -> SubtaskResult:
        agent_id = assignment.agent_id
        if not self.registry.has(agent_id):
            raise KeyError(f"Agent '{agent_id}' not registered")
        if not self.registry.try_get_adapter(agent_id):
            raise RuntimeError(f"Adapter for '{agent_id}' not instantiated")

        context, task = self._build_context(
            assignment=assignment,
            graph=graph,
            parent_results=parent_results,
            timeout_seconds=timeout_seconds,
            metadata=metadata,
        )
        wrapper = self.get_safety_wrapper(agent_id)
        start = datetime.now(UTC)

        try:
            result = await self._run_with_timeout(wrapper, task, context, timeout_seconds)
        except TimeoutError:
            self._record_failure(
                agent_id=agent_id,
                node_id=assignment.node_id,
                workflow_id=context.workflow_id,
                task=task,
                start=start,
                error_type="timeout",
                error_message=f"Execution exceeded {timeout_seconds}s",
            )
            return SubtaskResult(
                node_id=assignment.node_id,
                agent_id=agent_id,
                output="",
                artifacts=[],
                metadata={"error": "timeout", "timeout": True},
            )
        except Exception as exc:  # noqa: BLE001
            self._record_failure(
                agent_id=agent_id,
                node_id=assignment.node_id,
                workflow_id=context.workflow_id,
                task=task,
                start=start,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            return SubtaskResult(
                node_id=assignment.node_id,
                agent_id=agent_id,
                output="",
                artifacts=[],
                metadata={"error": str(exc), "exception": type(exc).__name__},
            )

        self._record_success(
            agent_id=agent_id,
            node_id=assignment.node_id,
            workflow_id=context.workflow_id,
            task=task,
            start=start,
            result=result,
        )
        return result

    async def _run_with_timeout(
        self,
        wrapper: SafetyWrapper,
        task: dict[str, Any],
        context: ExecutionContext,
        timeout_seconds: float,
    ) -> SubtaskResult:
        """Execute the wrapper in a thread with a timeout, yielding control to the event loop."""
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, lambda: wrapper.execute(task=task, context=context))
        return await asyncio.wait_for(future, timeout=timeout_seconds)

    async def execute_subtasks_batch(
        self,
        *,
        assignments: list[SubtaskAssignment],
        graph: TaskGraph,
        parent_results: dict[str, SubtaskResult] | None = None,
        max_concurrency: int = 4,
    ) -> list[SubtaskResult]:
        sem = asyncio.Semaphore(max_concurrency)

        async def _one(a: SubtaskAssignment) -> SubtaskResult:
            async with sem:
                return await self.execute_subtask(
                    assignment=a,
                    graph=graph,
                    parent_results=parent_results,
                )

        return await asyncio.gather(*[_one(a) for a in assignments])
