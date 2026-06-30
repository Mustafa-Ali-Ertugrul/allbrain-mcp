from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from allbrain.workflow.models import SubtaskResult, TaskGraph, TaskNode, WorkflowStatus
from allbrain.workflow.state_machine import WorkflowStateMachine


@dataclass
class RecoveryDecision:
    action: str  # "retry", "block", "skip"
    node_id: str
    retry_count: int
    max_retries: int
    delay_seconds: float = 0.0
    affected_nodes: list[str] = field(default_factory=list)
    reason: str = ""


class RecoveryManager:
    def __init__(self, max_retries: int = 3, backoff_base: float = 2.0, max_delay: float = 300.0):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_delay = max_delay

    def handle_failure(
        self,
        *,
        graph: TaskGraph,
        node_id: str,
        error: str,
        state_machine: WorkflowStateMachine | None = None,
    ) -> RecoveryDecision:
        node = graph.nodes.get(node_id)
        if node is None:
            return RecoveryDecision(
                action="skip",
                node_id=node_id,
                retry_count=0,
                max_retries=self.max_retries,
                reason=f"Node '{node_id}' not found in graph",
            )

        node.retry_count += 1

        if node.retry_count <= node.max_retries:
            delay = min(self.backoff_base**node.retry_count, self.max_delay)
            if state_machine is not None:
                state_machine.transition(node_id, WorkflowStatus.FAILED, reason=f"failure: {error}")
                state_machine.transition(node_id, WorkflowStatus.READY, reason=f"retry_scheduled: {error}")
            else:
                node.status = WorkflowStatus.READY
            return RecoveryDecision(
                action="retry",
                node_id=node_id,
                retry_count=node.retry_count,
                max_retries=node.max_retries,
                delay_seconds=delay,
                reason=f"Retry {node.retry_count}/{node.max_retries}: {error}",
            )

        affected = self._cascade_block(graph, node_id, state_machine)
        return RecoveryDecision(
            action="block",
            node_id=node_id,
            retry_count=node.retry_count,
            max_retries=node.max_retries,
            affected_nodes=affected,
            reason=f"Retry budget exhausted ({node.max_retries}). Cascading block to successors.",
        )

    def resume_workflow(
        self,
        *,
        graph: TaskGraph,
        completed_results: dict[str, SubtaskResult],
        state_machine: WorkflowStateMachine | None = None,
    ) -> TaskGraph:
        for node_id, result in completed_results.items():
            if node_id in graph.nodes:
                node = graph.nodes[node_id]
                node.result = result
                if state_machine is not None:
                    state_machine.transition(node_id, WorkflowStatus.COMPLETED, reason="resume_replay")
                else:
                    node.status = WorkflowStatus.COMPLETED

        for node in graph.nodes.values():
            if node.status == WorkflowStatus.RUNNING:
                if state_machine is not None:
                    state_machine.transition(node.node_id, WorkflowStatus.READY, reason="resume_reset")
                else:
                    node.status = WorkflowStatus.READY

        for node in graph.nodes.values():
            if node.status == WorkflowStatus.PENDING:
                preds = graph.predecessors(node.node_id)
                if not preds or all(p.status == WorkflowStatus.COMPLETED for p in preds):
                    if state_machine is not None:
                        can, _ = state_machine.can_transition(node.node_id, WorkflowStatus.READY)
                        if can:
                            state_machine.transition(node.node_id, WorkflowStatus.READY, reason="resume_ready")
                    else:
                        node.status = WorkflowStatus.READY

        return graph

    def _cascade_block(
        self,
        graph: TaskGraph,
        node_id: str,
        state_machine: WorkflowStateMachine | None = None,
    ) -> list[str]:
        affected: list[str] = []
        if state_machine is not None:
            state_machine.transition(node_id, WorkflowStatus.BLOCKED, reason="retry_exhausted")
        else:
            graph.nodes[node_id].status = WorkflowStatus.BLOCKED

        queue = [node_id]
        visited = {node_id}
        while queue:
            current = queue.pop(0)
            for succ in graph.successors(current):
                if succ.node_id not in visited and succ.status not in {
                    WorkflowStatus.COMPLETED,
                    WorkflowStatus.BLOCKED,
                }:
                    visited.add(succ.node_id)
                    affected.append(succ.node_id)
                    if state_machine is not None:
                        state_machine.transition(
                            succ.node_id, WorkflowStatus.BLOCKED, reason=f"predecessor_blocked: {current}"
                        )
                    else:
                        succ.status = WorkflowStatus.BLOCKED
                    queue.append(succ.node_id)
        return affected
