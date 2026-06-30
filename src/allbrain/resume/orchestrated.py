from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.orchestrator import DeterministicScheduler, TaskGraphBuilder, TaskStateReducer
from allbrain.orchestrator.metrics import AgentPerformanceReducer
from allbrain.orchestrator.state import AgentStateBuilder


class OrchestratedResumeEngine:
    def __init__(
        self,
        task_reducer: TaskStateReducer | None = None,
        task_graph_builder: TaskGraphBuilder | None = None,
        scheduler: DeterministicScheduler | None = None,
    ):
        self.task_reducer = task_reducer or TaskStateReducer()
        self.task_graph_builder = task_graph_builder or TaskGraphBuilder()
        self.scheduler = scheduler or DeterministicScheduler()
        self.metrics_reducer = AgentPerformanceReducer()
        self.agent_state_builder = AgentStateBuilder()

    def build(self, *, events: list[EventRead], base: dict[str, Any] | None = None) -> dict[str, Any]:
        task_state = self.task_reducer.build(events)
        metrics = self.metrics_reducer.reduce(events)
        return self.build_from_task_state(task_state=task_state, base=base, events=events, metrics=metrics)

    def build_from_task_state(
        self,
        *,
        task_state: dict[str, Any],
        base: dict[str, Any] | None = None,
        events: list[EventRead] | None = None,
        metrics: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        metrics = metrics if metrics is not None else self.metrics_reducer.reduce(events or [])
        task_graph = self.task_graph_builder.build(task_state)
        assignment_view = {"agent_queue": task_state["agent_queue"]}
        decision_view = self._decision_view(task_state, events=events or [], metrics=metrics)
        agent_state = self.agent_state_builder.build(metrics=metrics, task_state=task_state)
        return {
            "global_view": base or {},
            "task_view": task_state,
            "task_graph": task_graph,
            "assignment_view": assignment_view,
            "handoff_view": {"handoffs": task_state["handoffs"], "count": len(task_state["handoffs"])},
            "agent_state": agent_state,
            "scheduler_state": {"agent_state": agent_state},
            "decision_view": decision_view,
        }

    def _decision_view(
        self,
        task_state: dict[str, Any],
        *,
        events: list[EventRead],
        metrics: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        blocked = [
            task for task in task_state.get("tasks", {}).values() if task.get("status") in {"blocked", "failed"}
        ]
        if blocked:
            blocked.sort(key=lambda task: (-int(task.get("priority") or 0), task["task_id"]))
            task = blocked[0]
            owner = task.get("owner")
            if owner:
                try:
                    recommendation = self.scheduler.choose_agent(
                        task=task,
                        task_state=task_state,
                        exclude_agent_id=owner,
                        events=events,
                        metrics=metrics,
                    )
                except ValueError:
                    return {
                        "next_step": f"no eligible agent for handoff of {task['task_id']}",
                        "required_action": "escalate",
                        "task_id": task["task_id"],
                        "confidence": 0.5,
                    }
                return {
                    "next_step": f"handoff task {task['task_id']} to {recommendation['agent_id']}",
                    "required_action": "handoff_task",
                    "task_id": task["task_id"],
                    "recommended_agent": recommendation["agent_id"],
                    "score": recommendation["score"],
                    "breakdown": recommendation["breakdown"],
                    "confidence": 0.85,
                }
            return {
                "next_step": f"assign blocked task {task['task_id']}",
                "required_action": "assign_task",
                "task_id": task["task_id"],
                "confidence": 0.7,
            }
        open_tasks = [
            task for task in task_state.get("tasks", {}).values() if task.get("status") not in {"completed", "failed"}
        ]
        if open_tasks:
            open_tasks.sort(key=lambda task: (-int(task.get("priority") or 0), task["task_id"]))
            task = open_tasks[0]
            return {
                "next_step": f"continue task {task['task_id']}",
                "required_action": "continue",
                "task_id": task["task_id"],
                "confidence": 1.0,
            }
        return {
            "next_step": "no active task",
            "required_action": "none",
            "confidence": 1.0,
        }
