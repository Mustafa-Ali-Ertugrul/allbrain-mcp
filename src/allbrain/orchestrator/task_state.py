from __future__ import annotations

from copy import deepcopy
from typing import Any

from uuid6 import uuid7

from allbrain.events import EventType
from allbrain.models.schemas import EventRead

TASK_EVENT_TYPES = {
    EventType.TASK_CREATED.value,
    EventType.TASK_ASSIGNED.value,
    EventType.TASK_STARTED.value,
    EventType.TASK_BLOCKED.value,
    EventType.TASK_COMPLETED.value,
    EventType.TASK_FAILED.value,
    EventType.TASK_DEPENDENCY_ADDED.value,
    EventType.TASK_PRIORITY_CHANGED.value,
    EventType.TASK_UPDATED.value,
    EventType.TASK_DELETED.value,
    EventType.HANDOFF_CREATED.value,
    EventType.SUBTASK_CREATED.value,
    EventType.SUBTASK_STARTED.value,
    EventType.SUBTASK_COMPLETED.value,
    EventType.SUBTASK_FAILED.value,
    EventType.WORKFLOW_CREATED.value,
    EventType.WORKFLOW_STARTED.value,
    EventType.WORKFLOW_COMPLETED.value,
    EventType.WORKFLOW_FAILED.value,
    EventType.RESULT_AGGREGATED.value,
    EventType.WORKFLOW_STATE_CHANGED.value,
    EventType.RETRY_SCHEDULED.value,
    EventType.AGENT_REGISTERED.value,
    EventType.AGENT_HEALTH_CHANGED.value,
    EventType.AGENT_EXECUTION_STARTED.value,
    EventType.AGENT_EXECUTION_COMPLETED.value,
    EventType.AGENT_EXECUTION_FAILED.value,
    EventType.COST_CEILING_EXCEEDED.value,
    EventType.CAPABILITY_UPDATED.value,
    EventType.QUEUE_ITEM_ENQUEUED.value,
    EventType.QUEUE_ITEM_DEQUEUED.value,
    EventType.WORKER_STARTED.value,
    EventType.WORKER_STOPPED.value,
}


class TaskStateReducer:
    """Reducer for building task state from event history.

    Applies event-sourcing pattern to reconstruct task state, dependencies,
    and handoffs from immutable event log. Uses handler pattern for
    extensibility and testability.
    """

    def __init__(self) -> None:
        """Initialize task state reducer with event handlers."""
        self._handlers: dict[str, Any] = {
            EventType.TASK_CREATED.value: self._handle_task_created,
            EventType.TASK_ASSIGNED.value: self._handle_task_assigned,
            EventType.TASK_STARTED.value: self._handle_task_started,
            EventType.TASK_BLOCKED.value: self._handle_task_blocked,
            EventType.TASK_COMPLETED.value: self._handle_task_completed,
            EventType.TASK_FAILED.value: self._handle_task_failed,
            EventType.TASK_PRIORITY_CHANGED.value: self._handle_priority_changed,
            EventType.TASK_UPDATED.value: self._handle_task_updated,
            EventType.TASK_DELETED.value: self._handle_task_deleted,
            EventType.TASK_DEPENDENCY_ADDED.value: self._handle_dependency_added,
            EventType.HANDOFF_CREATED.value: self._handle_handoff_created,
            EventType.SUBTASK_CREATED.value: self._handle_subtask,
            EventType.SUBTASK_STARTED.value: self._handle_subtask,
            EventType.SUBTASK_COMPLETED.value: self._handle_subtask,
            EventType.SUBTASK_FAILED.value: self._handle_subtask,
            EventType.WORKFLOW_STATE_CHANGED.value: self._handle_workflow_state,
            EventType.RETRY_SCHEDULED.value: self._handle_retry,
            EventType.AGENT_EXECUTION_STARTED.value: self._handle_agent_execution,
            EventType.AGENT_EXECUTION_COMPLETED.value: self._handle_agent_execution,
            EventType.AGENT_EXECUTION_FAILED.value: self._handle_agent_execution,
            EventType.AGENT_REGISTERED.value: self._handle_agent_registered,
            EventType.AGENT_HEALTH_CHANGED.value: self._handle_agent_health,
            EventType.COST_CEILING_EXCEEDED.value: self._handle_cost_violation,
            EventType.CAPABILITY_UPDATED.value: self._handle_capability_update,
        }

    def build(self, events: list[EventRead]) -> dict[str, Any]:
        tasks: dict[str, dict[str, Any]] = {}
        dependencies: list[dict[str, str]] = []
        handoffs: list[dict[str, Any]] = []
        for event in events:
            if event.type not in TASK_EVENT_TYPES:
                continue
            payload = event.payload
            task_id = payload.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                continue
            task = tasks.setdefault(task_id, self._new_task(task_id))
            self._apply_event(task, event, dependencies, handoffs)
        return self._finalize(tasks=tasks, dependencies=dependencies, handoffs=handoffs)

    def apply_events(self, base_state: dict[str, Any], events: list[EventRead]) -> dict[str, Any]:
        tasks = deepcopy(base_state.get("tasks", {}))
        dependencies = deepcopy(base_state.get("dependencies", []))
        handoffs = deepcopy(base_state.get("handoffs", []))
        for event in events:
            if event.type not in TASK_EVENT_TYPES:
                continue
            task_id = event.payload.get("task_id")
            if not isinstance(task_id, str) or not task_id:
                continue
            task = tasks.setdefault(task_id, self._new_task(task_id))
            self._apply_event(task, event, dependencies, handoffs)
        return self._finalize(tasks=tasks, dependencies=dependencies, handoffs=handoffs)

    @staticmethod
    def new_task_id() -> str:
        return str(uuid7())

    def _new_task(self, task_id: str) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "goal": None,
            "kind": "implementation",
            "related_files": [],
            "priority": 3,
            "status": "created",
            "owner": None,
            "ownership_history": [],
            "history": [],
            "blocked_reason": None,
            "failure": None,
        }

    def _apply_event(
        self,
        task: dict[str, Any],
        event: EventRead,
        dependencies: list[dict[str, str]],
        handoffs: list[dict[str, Any]],
    ) -> None:
        """Apply event to task state using registered handler.

        Delegates to event-specific handler functions. All handlers
        mutate task/dependencies/handoffs in-place for performance.
        """
        task["history"].append({"event_id": event.id, "type": event.type, "created_at": event.created_at.isoformat()})

        handler = self._handlers.get(event.type)
        if handler:
            handler(task, event, dependencies, handoffs)

    def _handle_task_created(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_CREATED event - initialize task with goal and files."""
        payload = event.payload
        task["goal"] = payload.get("goal") or task["goal"]
        task["kind"] = payload.get("kind") or task["kind"]
        task["related_files"] = list(dict.fromkeys(payload.get("related_files") or task["related_files"]))
        task["priority"] = payload.get("priority", task["priority"])
        task["status"] = "created"

    def _handle_task_assigned(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_ASSIGNED event - assign agent and update ownership."""
        payload = event.payload
        agent_id = payload.get("agent_id") or event.agent_id
        task["owner"] = agent_id
        if agent_id and (not task["ownership_history"] or task["ownership_history"][-1] != agent_id):
            task["ownership_history"].append(agent_id)
        task["status"] = "assigned"

    def _handle_task_started(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_STARTED event - mark task as started with owner."""
        payload = event.payload
        task["status"] = "started"
        task["owner"] = event.agent_id or task["owner"]
        if event.agent_id and (not task["ownership_history"] or task["ownership_history"][-1] != event.agent_id):
            task["ownership_history"].append(event.agent_id)
        task["goal"] = payload.get("task") or payload.get("goal") or task["goal"]

    def _handle_task_blocked(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_BLOCKED event - mark task as blocked with reason."""
        task["status"] = "blocked"
        task["blocked_reason"] = event.payload.get("reason")

    def _handle_task_completed(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_COMPLETED event - mark task as completed."""
        task["status"] = "completed"

    def _handle_task_failed(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_FAILED event - mark task as failed with error."""
        payload = event.payload
        task["status"] = "failed"
        task["failure"] = payload.get("error") or payload.get("reason")

    def _handle_priority_changed(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_PRIORITY_CHANGED event - update task priority."""
        task["priority"] = event.payload.get("new", task["priority"])

    def _handle_task_updated(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_UPDATED event - update task goal, kind, or related_files."""
        payload = event.payload
        if "goal" in payload and payload["goal"] is not None:
            task["goal"] = payload["goal"]
        if "kind" in payload and payload["kind"] is not None:
            task["kind"] = payload["kind"]
        if "related_files" in payload and payload["related_files"] is not None:
            task["related_files"] = list(dict.fromkeys(payload["related_files"]))

    def _handle_task_deleted(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_DELETED event - mark task as deleted."""
        task["status"] = "deleted"
        task["deleted_reason"] = event.payload.get("reason")

    def _handle_dependency_added(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle TASK_DEPENDENCY_ADDED event - add dependency edge."""
        depends_on = event.payload.get("depends_on")
        if isinstance(depends_on, str) and depends_on:
            edge = {"task_id": task["task_id"], "depends_on": depends_on}
            if edge not in deps:
                deps.append(edge)

    def _handle_handoff_created(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle HANDOFF_CREATED event - record agent handoff."""
        payload = event.payload
        handoff = {
            "task_id": task["task_id"],
            "from_agent": payload.get("from_agent"),
            "to_agent": payload.get("to_agent"),
            "reason": payload.get("reason"),
            "event_id": event.id,
        }
        handoffs.append(handoff)

    def _handle_subtask(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle SUBTASK_* events - manage subtask lifecycle."""
        payload = event.payload
        subtask_id = payload.get("node_id")
        subtasks = task.setdefault("subtasks", {})
        sub = subtasks.setdefault(
            subtask_id,
            {
                "node_id": subtask_id,
                "status": "pending",
                "agent_id": None,
                "goal": payload.get("goal"),
                "score": payload.get("score"),
                "reason": payload.get("reason"),
            },
        )
        if event.type == EventType.SUBTASK_CREATED.value:
            sub["status"] = "pending"
            sub["goal"] = payload.get("goal") or sub.get("goal")
        elif event.type == EventType.SUBTASK_STARTED.value:
            sub["status"] = "running"
            sub["agent_id"] = payload.get("agent_id") or event.agent_id
        elif event.type == EventType.SUBTASK_COMPLETED.value:
            sub["status"] = "completed"
            sub["agent_id"] = payload.get("agent_id") or event.agent_id
        elif event.type == EventType.SUBTASK_FAILED.value:
            sub["status"] = "failed"
            sub["reason"] = payload.get("reason")
            sub["retry_count"] = payload.get("retry_count", 0)

    def _handle_workflow_state(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle WORKFLOW_STATE_CHANGED event - track workflow transitions."""
        payload = event.payload
        task.setdefault("workflow_states", []).append(
            {
                "node_id": payload.get("node_id"),
                "previous_status": payload.get("previous_status"),
                "new_status": payload.get("new_status"),
                "reason": payload.get("reason"),
                "agent_id": payload.get("agent_id") or event.agent_id,
            }
        )

    def _handle_retry(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle RETRY_SCHEDULED event - record retry attempts."""
        payload = event.payload
        task.setdefault("retries", []).append(
            {
                "node_id": payload.get("node_id"),
                "retry_count": payload.get("retry_count"),
                "reason": payload.get("reason"),
            }
        )

    def _handle_agent_execution(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle AGENT_EXECUTION_* events - track agent execution metrics."""
        payload = event.payload
        task.setdefault("agent_executions", []).append(
            {
                "node_id": payload.get("node_id"),
                "agent_id": payload.get("agent_id"),
                "event_type": event.type,
                "duration_ms": payload.get("duration_ms"),
                "input_tokens": payload.get("input_tokens"),
                "output_tokens": payload.get("output_tokens"),
                "cost_usd": payload.get("cost_usd"),
                "success": payload.get("success"),
                "error": payload.get("error"),
            }
        )

    def _handle_agent_registered(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle AGENT_REGISTERED event - track registered agents."""
        payload = event.payload
        task.setdefault("registered_agents", []).append(
            {
                "agent_id": payload.get("agent_id"),
                "provider": payload.get("provider"),
                "version": payload.get("version"),
            }
        )

    def _handle_agent_health(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle AGENT_HEALTH_CHANGED event - track agent health changes."""
        payload = event.payload
        task.setdefault("agent_health", []).append(
            {
                "agent_id": payload.get("agent_id"),
                "status": payload.get("status"),
                "consecutive_failures": payload.get("consecutive_failures"),
            }
        )

    def _handle_cost_violation(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle COST_CEILING_EXCEEDED event - track cost violations."""
        payload = event.payload
        task.setdefault("cost_violations", []).append(
            {
                "agent_id": payload.get("agent_id"),
                "estimated_cost": payload.get("estimated_cost"),
                "limit": payload.get("limit"),
            }
        )

    def _handle_capability_update(
        self, task: dict[str, Any], event: EventRead, deps: list[dict[str, str]], handoffs: list[dict[str, Any]]
    ) -> None:
        """Handle CAPABILITY_UPDATED event - track capability changes."""
        payload = event.payload
        task.setdefault("capability_updates", []).append(
            {
                "agent_id": payload.get("agent_id"),
                "domain": payload.get("domain"),
                "capability": payload.get("capability"),
            }
        )

    def _agent_queue(self, tasks: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
        queue: dict[str, list[str]] = {}
        for task_id, task in tasks.items():
            owner = task.get("owner")
            if not owner or task.get("status") in {"completed", "failed"}:
                continue
            queue.setdefault(owner, []).append(task_id)
        for task_ids in queue.values():
            task_ids.sort(key=lambda item: (-int(tasks[item].get("priority", 0)), item))
        return dict(sorted(queue.items()))

    def _finalize(
        self,
        *,
        tasks: dict[str, dict[str, Any]],
        dependencies: list[dict[str, str]],
        handoffs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        queue = self._agent_queue(tasks)
        return {
            "tasks": tasks,
            "dependencies": dependencies,
            "handoffs": handoffs,
            "agent_queue": queue,
            "open_task_ids": [
                task_id for task_id, task in tasks.items() if task["status"] not in {"completed", "failed", "deleted"}
            ],
            "completed_task_ids": [task_id for task_id, task in tasks.items() if task["status"] == "completed"],
            "deleted_task_ids": [task_id for task_id, task in tasks.items() if task["status"] == "deleted"],
        }
