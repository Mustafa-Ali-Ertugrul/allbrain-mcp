from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from allbrain.orchestrator.scoring import SchedulerV1
from allbrain.domains.collaboration.workflow.graph import DependencyEngine
from allbrain.domains.collaboration.workflow.models import TaskGraph, TaskNode, WorkflowStatus


@dataclass
class SubtaskAssignment:
    node_id: str
    agent_id: str
    score: float
    breakdown: dict[str, Any] = field(default_factory=dict)
    reason: str = "highest_score"


class SubtaskScheduler:
    def __init__(
        self,
        base_scheduler: SchedulerV1 | None = None,
        dependency_engine: DependencyEngine | None = None,
    ):
        self.base_scheduler = base_scheduler or SchedulerV1()
        self.dependency_engine = dependency_engine or DependencyEngine()

    def next_subtasks(
        self,
        *,
        graph: TaskGraph,
        candidate_agents: list[str],
        metrics: dict[str, dict[str, Any]],
        max_parallel: int = 3,
        task_state: dict[str, Any] | None = None,
        skip_node_ids: set[str] | None = None,
    ) -> list[SubtaskAssignment]:
        ready = self.dependency_engine.ready_set(graph)
        if not ready:
            return []

        skip = skip_node_ids or set()
        assignments: list[SubtaskAssignment] = []
        for node in ready:
            if node.status not in {WorkflowStatus.PENDING, WorkflowStatus.READY}:
                continue
            if node.node_id in skip:
                continue
            task = {
                "task_id": node.task_id,
                "goal": node.goal,
                "kind": node.kind,
                "priority": node.priority,
            }
            result = self.base_scheduler.assign_task(
                task=task,
                candidate_agents=candidate_agents,
                metrics=metrics,
                task_state=task_state,
            )
            assignments.append(
                SubtaskAssignment(
                    node_id=node.node_id,
                    agent_id=result["agent_id"],
                    score=result["score"],
                    breakdown=result.get("breakdown", {}),
                    reason=result.get("reason", "highest_score"),
                )
            )

        assignments.sort(key=lambda a: -a.score)
        return assignments[:max_parallel]

    def score_subtask(
        self,
        *,
        node: TaskNode,
        candidate_agents: list[str],
        metrics: dict[str, dict[str, Any]],
        task_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        task = {
            "task_id": node.task_id,
            "goal": node.goal,
            "kind": node.kind,
            "priority": node.priority,
        }
        return [
            self.base_scheduler.score_agent(
                agent_id=agent_id,
                task=task,
                metrics=metrics,
                task_state=task_state,
            )
            for agent_id in candidate_agents
        ]
