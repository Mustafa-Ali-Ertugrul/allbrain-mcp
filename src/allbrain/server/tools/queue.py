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


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def claim_task(
        workflow_id: str | None = None,
        lease_ttl_seconds: int = 120,
    ) -> dict[str, Any]:
        """Claim a task from the distributed queue for exclusive processing.

        Use this in worker/actor patterns where multiple agents compete for tasks.
        Only one agent can successfully claim a given queue_item at a time.

        Side effects: Marks a task as "claimed" with a lease that expires after
        lease_ttl_seconds. Creates a TASK_CLAIMED event.

        Args:
            workflow_id: Optional workflow ID to claim a task for (allows scoping).
            lease_ttl_seconds: Lease duration in seconds (default 120). The task will
                be automatically released if not completed or renewed within this time.

        Returns:
            Claim result with queue_item_id, lease_id, and task details if successful.
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
        """Extend the lease on a claimed task to prevent automatic release.

        Use this when a task is taking longer than expected. Call periodically
        during long-running operations to keep the task "claimed" by your agent.

        Side effects: Updates the lease expiry timestamp for the queue item.

        Args:
            queue_item_id: ID of the queue item to renew.
            lease_id: Current lease ID (obtained from claim_task).
            lease_ttl_seconds: Extended lease duration (default 120).

        Returns:
            Updated lease information with new expiry timestamp.
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

    @mcp.tool
    def complete_task(
        queue_item_id: str,
        lease_id: str,
        output: str,
        artifacts: list[str] | None = None,
    ) -> dict[str, Any]:
        """Mark a claimed task as completed with output and optional artifacts.

        Use this to finalize a task after successful completion. This is the final
        step in the worker pattern: claim -> process -> complete.

        Side effects: Creates a TASK_COMPLETED event, releases the lease, and
        makes the task unavailable for other workers. Output is sanitized for safety.

        Args:
            queue_item_id: ID of the queue item to complete.
            lease_id: Current lease ID (must match the claiming agent).
            output: Task output/result string (will be sanitized for safety).
            artifacts: Optional list of artifact file paths produced by the task.

        Returns:
            Completion confirmation with task_id, output, and artifacts list.
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
        """Mark a claimed task as failed with a reason, optionally requeuing it.

        Use this when a task cannot be completed due to errors, timeouts, or
        unexpected conditions. If requeue=True, the task returns to the queue
        for another worker to attempt.

        Side effects: Creates a TASK_FAILED event in the event log. If requeue=True,
        the task becomes available for other workers. Output is sanitized for safety.

        Args:
            queue_item_id: ID of the queue item to fail.
            lease_id: Current lease ID (must match the claiming agent).
            reason: Failure reason description (will be sanitized; helpful for debugging).
            requeue: Whether to make the task available for other workers (default True).
                Set to False for permanent failure/cancellation.

        Returns:
            Failure confirmation with task_id, reason, and requeue status.
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
