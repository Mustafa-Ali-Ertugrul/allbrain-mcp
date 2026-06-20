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
        payload = event.payload
        task["history"].append({"event_id": event.id, "type": event.type, "created_at": event.created_at.isoformat()})
        if event.type == EventType.TASK_CREATED.value:
            task["goal"] = payload.get("goal") or task["goal"]
            task["kind"] = payload.get("kind") or task["kind"]
            task["related_files"] = list(dict.fromkeys(payload.get("related_files") or task["related_files"]))
            task["priority"] = payload.get("priority", task["priority"])
            task["status"] = "created"
        elif event.type == EventType.TASK_ASSIGNED.value:
            agent_id = payload.get("agent_id") or event.agent_id
            task["owner"] = agent_id
            if agent_id and (not task["ownership_history"] or task["ownership_history"][-1] != agent_id):
                task["ownership_history"].append(agent_id)
            task["status"] = "assigned"
        elif event.type == EventType.TASK_STARTED.value:
            task["status"] = "started"
            task["owner"] = event.agent_id or task["owner"]
            if event.agent_id and (not task["ownership_history"] or task["ownership_history"][-1] != event.agent_id):
                task["ownership_history"].append(event.agent_id)
            task["goal"] = payload.get("task") or payload.get("goal") or task["goal"]
        elif event.type == EventType.TASK_BLOCKED.value:
            task["status"] = "blocked"
            task["blocked_reason"] = payload.get("reason")
        elif event.type == EventType.TASK_COMPLETED.value:
            task["status"] = "completed"
        elif event.type == EventType.TASK_FAILED.value:
            task["status"] = "failed"
            task["failure"] = payload.get("error") or payload.get("reason")
        elif event.type == EventType.TASK_PRIORITY_CHANGED.value:
            task["priority"] = payload.get("new", task["priority"])
        elif event.type == EventType.TASK_DEPENDENCY_ADDED.value:
            depends_on = payload.get("depends_on")
            if isinstance(depends_on, str) and depends_on:
                edge = {"task_id": task["task_id"], "depends_on": depends_on}
                if edge not in dependencies:
                    dependencies.append(edge)
        elif event.type == EventType.HANDOFF_CREATED.value:
            handoff = {
                "task_id": task["task_id"],
                "from_agent": payload.get("from_agent"),
                "to_agent": payload.get("to_agent"),
                "reason": payload.get("reason"),
                "event_id": event.id,
            }
            handoffs.append(handoff)
        elif event.type in {
            EventType.SUBTASK_CREATED.value,
            EventType.SUBTASK_STARTED.value,
            EventType.SUBTASK_COMPLETED.value,
            EventType.SUBTASK_FAILED.value,
        }:
            subtask_id = payload.get("node_id")
            subtasks = task.setdefault("subtasks", {})
            sub = subtasks.setdefault(subtask_id, {
                "node_id": subtask_id,
                "status": "pending",
                "agent_id": None,
                "goal": payload.get("goal"),
                "score": payload.get("score"),
                "reason": payload.get("reason"),
            })
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
        elif event.type == EventType.WORKFLOW_STATE_CHANGED.value:
            task.setdefault("workflow_states", []).append({
                "node_id": payload.get("node_id"),
                "previous_status": payload.get("previous_status"),
                "new_status": payload.get("new_status"),
                "reason": payload.get("reason"),
                "agent_id": payload.get("agent_id") or event.agent_id,
            })
        elif event.type == EventType.RETRY_SCHEDULED.value:
            task.setdefault("retries", []).append({
                "node_id": payload.get("node_id"),
                "retry_count": payload.get("retry_count"),
                "reason": payload.get("reason"),
            })
        elif event.type in {
            EventType.AGENT_EXECUTION_STARTED.value,
            EventType.AGENT_EXECUTION_COMPLETED.value,
            EventType.AGENT_EXECUTION_FAILED.value,
        }:
            task.setdefault("agent_executions", []).append({
                "node_id": payload.get("node_id"),
                "agent_id": payload.get("agent_id"),
                "event_type": event.type,
                "duration_ms": payload.get("duration_ms"),
                "input_tokens": payload.get("input_tokens"),
                "output_tokens": payload.get("output_tokens"),
                "cost_usd": payload.get("cost_usd"),
                "success": payload.get("success"),
                "error": payload.get("error"),
            })
        elif event.type == EventType.AGENT_REGISTERED.value:
            task.setdefault("registered_agents", []).append({
                "agent_id": payload.get("agent_id"),
                "provider": payload.get("provider"),
                "version": payload.get("version"),
            })
        elif event.type == EventType.AGENT_HEALTH_CHANGED.value:
            task.setdefault("agent_health", []).append({
                "agent_id": payload.get("agent_id"),
                "status": payload.get("status"),
                "consecutive_failures": payload.get("consecutive_failures"),
            })
        elif event.type == EventType.COST_CEILING_EXCEEDED.value:
            task.setdefault("cost_violations", []).append({
                "agent_id": payload.get("agent_id"),
                "estimated_cost": payload.get("estimated_cost"),
                "limit": payload.get("limit"),
            })
        elif event.type == EventType.CAPABILITY_UPDATED.value:
            task.setdefault("capability_updates", []).append({
                "agent_id": payload.get("agent_id"),
                "domain": payload.get("domain"),
                "capability": payload.get("capability"),
            })

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
                task_id
                for task_id, task in tasks.items()
                if task["status"] not in {"completed", "failed"}
            ],
            "completed_task_ids": [
                task_id for task_id, task in tasks.items() if task["status"] == "completed"
            ],
        }
