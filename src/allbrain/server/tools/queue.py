from __future__ import annotations

from typing import Any

from allbrain.models.schemas import ToolResult
from allbrain.security.redaction import sanitize_text
from allbrain.server.context import BrainContext
from allbrain.server.queueing import QueueCoordinator


def _run(context: BrainContext, operation, **kwargs: Any) -> ToolResult:
    try:
        context.ensure_active_session()
        return ToolResult(ok=True, data=operation(**kwargs))
    except (ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def _register_queue_claim_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def claim_task(
        workflow_id: str | None = None,
        lease_ttl_seconds: int = 120,
    ) -> dict[str, Any]:
        """Claim the next available task from the distributed queue.

        Atomically dequeues a task assigned to this agent, establishing a
        lease that prevents other workers from claiming it for lease_ttl_seconds.
        The lease must be periodically renewed or the task reclaimed.

        When to use: in multi-worker deployments where agents pull tasks from
        a shared queue. Call before starting work on a queued task.
        """
        coordinator = QueueCoordinator(context)
        return _run(
            context,
            coordinator.claim,
            agent_id=context.agent_name,
            server_instance_id=context.server_instance_id,
            workflow_id=workflow_id,
            lease_ttl_seconds=lease_ttl_seconds,
        ).model_dump(mode="json")

    @mcp.tool
    def renew_task_lease(
        queue_item_id: str,
        lease_id: str,
        lease_ttl_seconds: int = 120,
    ) -> dict[str, Any]:
        """Extend the lease on a claimed task to prevent reclamation.

        Resets the lease expiry timer, allowing the current worker to continue
        processing without losing the claim.

        When to use: periodically during long-running task execution to prevent
        other workers from claiming the task before it completes.
        """
        coordinator = QueueCoordinator(context)
        return _run(
            context,
            coordinator.renew,
            queue_item_id=queue_item_id,
            lease_id=lease_id,
            server_instance_id=context.server_instance_id,
            lease_ttl_seconds=lease_ttl_seconds,
        ).model_dump(mode="json")


def _register_queue_result_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def complete_task(
        queue_item_id: str,
        lease_id: str,
        output: str,
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        """Mark a claimed task as completed with output and artifacts.

        Releases the lease and records the task result in the event store.
        Sanitizes output text to prevent sensitive data leakage.

        When to use: after finishing work on a claimed task. Must provide the
        lease_id obtained from claim_task. Do NOT use for failure cases — use
        fail_task instead.
        """
        coordinator = QueueCoordinator(context)
        return _run(
            context,
            coordinator.complete,
            queue_item_id=queue_item_id,
            lease_id=lease_id,
            server_instance_id=context.server_instance_id,
            output=sanitize_text(output),
            artifacts=[sanitize_text(item) for item in (artifacts or [])],
        ).model_dump(mode="json")

    @mcp.tool
    def fail_task(
        queue_item_id: str,
        lease_id: str,
        reason: str,
        requeue: bool = True,
    ) -> dict[str, Any]:
        """Mark a claimed task as failed with an error reason.

        Releases the lease optionally requeues the task for retry. The reason
        text is sanitized to prevent sensitive data leakage.

        When to use: when work on a claimed task cannot continue due to an
        error. Set requeue=True for transient failures that may succeed on
        retry, False for permanent failures.
        """
        coordinator = QueueCoordinator(context)
        return _run(
            context,
            coordinator.fail,
            queue_item_id=queue_item_id,
            lease_id=lease_id,
            server_instance_id=context.server_instance_id,
            reason=sanitize_text(reason),
            requeue=requeue,
        ).model_dump(mode="json")


def register_tools(mcp, context: BrainContext) -> None:
    _register_queue_claim_tools(mcp, context)
    _register_queue_result_tools(mcp, context)
