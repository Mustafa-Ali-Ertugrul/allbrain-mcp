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
        """Claim a task from the distributed queue.

        Args:
            workflow_id: Optional workflow ID to claim a task for.
            lease_ttl_seconds: Lease time-to-live in seconds (default 120).

        Returns:
            Tool result as a JSON-serializable dict.
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
        """Extend lease on a claimed task.

        Args:
            queue_item_id: ID of the queue item to renew.
            lease_id: Current lease ID for authentication.
            lease_ttl_seconds: Extended lease time-to-live in seconds (default 120).

        Returns:
            Tool result as a JSON-serializable dict.
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
        """Mark a task as completed.

        Args:
            queue_item_id: ID of the queue item to complete.
            lease_id: Current lease ID for authentication.
            output: Task output string.
            artifacts: Optional list of artifact paths.

        Returns:
            Tool result as a JSON-serializable dict.
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
        """Mark a task as failed, optionally requeue.

        Args:
            queue_item_id: ID of the queue item to fail.
            lease_id: Current lease ID for authentication.
            reason: Failure reason description.
            requeue: Whether to requeue the task (default True).

        Returns:
            Tool result as a JSON-serializable dict.
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
