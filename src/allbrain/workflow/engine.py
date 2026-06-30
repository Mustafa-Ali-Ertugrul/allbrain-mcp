from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uuid6 import uuid7

from allbrain.workflow.aggregator import ResultAggregator
from allbrain.workflow.graph import DependencyEngine
from allbrain.workflow.models import (
    AggregatedResult,
    AggregationStrategy,
    EdgeType,
    SubtaskResult,
    TaskEdge,
    TaskGraph,
    TaskNode,
    WorkflowStatus,
)
from allbrain.workflow.recovery import RecoveryManager
from allbrain.workflow.scheduler import SubtaskScheduler
from allbrain.workflow.state_machine import WorkflowStateMachine


@dataclass
class StepResult:
    assignments: list[dict[str, Any]] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    recovered: list[dict[str, Any]] = field(default_factory=list)
    aggregated: AggregatedResult | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    is_done: bool = False


@dataclass
class WorkflowResult:
    success: bool
    graph: TaskGraph
    events: list[dict[str, Any]] = field(default_factory=list)
    aggregated: AggregatedResult | None = None
    error: str | None = None


class WorkflowEngine:
    def __init__(
        self,
        dependency_engine: DependencyEngine | None = None,
        scheduler: SubtaskScheduler | None = None,
        aggregator: ResultAggregator | None = None,
        recovery: RecoveryManager | None = None,
    ):
        self.dependency_engine = dependency_engine or DependencyEngine()
        self.scheduler = scheduler or SubtaskScheduler()
        self.aggregator = aggregator or ResultAggregator()
        self.recovery = recovery or RecoveryManager()

    def create_workflow(
        self,
        *,
        task_id: str,
        goal: str,
        subtasks: list[dict[str, Any]],
        edges: list[dict[str, str]],
        max_retries: int = 3,
    ) -> TaskGraph:
        self.dependency_engine.validate(TaskGraph())
        graph = TaskGraph(root_task_id=task_id)
        for st in subtasks:
            explicit_id = st.get("node_id")
            node = TaskNode(
                node_id=explicit_id if explicit_id else str(uuid7()),
                task_id=task_id,
                goal=st["goal"],
                kind=st.get("kind", "implementation"),
                priority=st.get("priority", 3),
                depth=st.get("depth", 0),
                parent_id=st.get("parent_id"),
                max_retries=max_retries,
                metadata=st.get("metadata", {}),
            )
            graph.add_node(node)
        for e in edges:
            graph.add_edge(
                TaskEdge(
                    from_id=e["from"],
                    to_id=e["to"],
                    edge_type=EdgeType(e.get("edge_type", "depends_on")),
                )
            )
        validation = self.dependency_engine.validate(graph)
        if not validation.valid:
            raise ValueError(f"Invalid workflow graph: {validation.errors}")
        for node in graph.nodes.values():
            preds = graph.predecessors(node.node_id)
            if not preds:
                node.status = WorkflowStatus.READY
        return graph

    def step(
        self,
        graph: TaskGraph,
        *,
        candidate_agents: list[str],
        metrics: dict[str, dict[str, Any]],
        task_state: dict[str, Any] | None = None,
        max_parallel: int = 3,
        failures: dict[str, str] | None = None,
        completions: dict[str, SubtaskResult] | None = None,
    ) -> StepResult:
        state_machine = WorkflowStateMachine(graph)
        result = StepResult()
        failures = failures or {}
        completions = completions or {}

        for node_id, fail_reason in failures.items():
            if node_id in graph.nodes and graph.nodes[node_id].status == WorkflowStatus.RUNNING:
                decision = self.recovery.handle_failure(
                    graph=graph,
                    node_id=node_id,
                    error=fail_reason,
                    state_machine=state_machine,
                )
                result.recovered.append(decision.__dict__)
                result.failed.append(node_id)
                result.events.append(
                    {
                        "type": "subtask_failed",
                        "node_id": node_id,
                        "reason": fail_reason,
                        "retry_count": decision.retry_count,
                    }
                )
                if decision.action == "block":
                    for affected in decision.affected_nodes:
                        result.events.append(
                            {
                                "type": "workflow_state_changed",
                                "node_id": affected,
                                "new_status": WorkflowStatus.BLOCKED.value,
                                "reason": f"cascade_from:{node_id}",
                            }
                        )

        for node_id, subtask_result in completions.items():
            if node_id in graph.nodes:
                node = graph.nodes[node_id]
                if node.status == WorkflowStatus.RUNNING:
                    node.result = subtask_result
                    tr = state_machine.transition(
                        node_id,
                        WorkflowStatus.COMPLETED,
                        reason="subtask_completed",
                        agent_id=subtask_result.agent_id,
                    )
                    result.completed.append(node_id)
                    result.events.extend(tr.events)

        ready = self.dependency_engine.ready_set(graph)
        for node in ready:
            if node.status == WorkflowStatus.READY:
                result.events.append(
                    {
                        "type": "subtask_ready",
                        "node_id": node.node_id,
                        "task_id": node.task_id,
                    }
                )

        skip_scheduling = set(result.failed)
        for r in result.recovered:
            skip_scheduling.add(r.get("node_id"))

        assignments = self.scheduler.next_subtasks(
            graph=graph,
            candidate_agents=candidate_agents,
            metrics=metrics,
            max_parallel=max_parallel,
            task_state=task_state,
            skip_node_ids=skip_scheduling,
        )
        for assignment in assignments:
            if assignment.node_id in skip_scheduling:
                continue
            state_machine.transition(
                assignment.node_id,
                WorkflowStatus.RUNNING,
                reason="subtask_scheduled",
                agent_id=assignment.agent_id,
            )
            result.assignments.append(assignment.__dict__)
            result.events.append(
                {
                    "type": "subtask_started",
                    "node_id": assignment.node_id,
                    "agent_id": assignment.agent_id,
                    "score": assignment.score,
                    "reason": assignment.reason,
                }
            )

        active_nodes = [
            n
            for n in graph.nodes.values()
            if n.status
            not in {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.BLOCKED,
                WorkflowStatus.FAILED,
            }
        ]
        if not active_nodes and not ready:
            result.is_done = True
            completed_nodes = [n for n in graph.nodes.values() if n.status == WorkflowStatus.COMPLETED]
            if completed_nodes:
                results = [n.result for n in completed_nodes if n.result]
                result.aggregated = self.aggregator.aggregate(
                    parent_task_id=graph.root_task_id or "unknown",
                    subtask_results=results,
                    strategy=AggregationStrategy.CONCAT,
                )
        return result

    def run(
        self,
        graph: TaskGraph,
        *,
        candidate_agents: list[str],
        metrics: dict[str, dict[str, Any]],
        task_state: dict[str, Any] | None = None,
        max_parallel: int = 3,
        max_steps: int = 100,
    ) -> WorkflowResult:
        all_events: list[dict[str, Any]] = []
        for _step in range(max_steps):
            step_result = self.step(
                graph,
                candidate_agents=candidate_agents,
                metrics=metrics,
                task_state=task_state,
                max_parallel=max_parallel,
            )
            all_events.extend(step_result.events)
            if step_result.is_done:
                all_failed_or_blocked = all(
                    n.status in {WorkflowStatus.FAILED, WorkflowStatus.BLOCKED} for n in graph.nodes.values()
                )
                return WorkflowResult(
                    success=not all_failed_or_blocked,
                    graph=graph,
                    events=all_events,
                    aggregated=step_result.aggregated,
                    error="All nodes failed or blocked" if all_failed_or_blocked else None,
                )

        return WorkflowResult(
            success=False,
            graph=graph,
            events=all_events,
            error=f"Workflow exceeded max_steps ({max_steps})",
        )

    def resume(
        self,
        graph: TaskGraph,
        *,
        completed_results: dict[str, SubtaskResult],
        candidate_agents: list[str],
        metrics: dict[str, dict[str, Any]],
        task_state: dict[str, Any] | None = None,
        max_parallel: int = 3,
    ) -> WorkflowResult:
        state_machine = WorkflowStateMachine(graph)
        self.recovery.resume_workflow(
            graph=graph,
            completed_results=completed_results,
            state_machine=state_machine,
        )
        return self.run(
            graph,
            candidate_agents=candidate_agents,
            metrics=metrics,
            task_state=task_state,
            max_parallel=max_parallel,
        )
