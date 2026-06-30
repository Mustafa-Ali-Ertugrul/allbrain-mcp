from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from allbrain.workflow.models import TaskGraph, TaskNode, WorkflowStatus


@dataclass
class TransitionResult:
    success: bool
    previous_status: WorkflowStatus | None = None
    new_status: WorkflowStatus | None = None
    errors: list[str] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


class WorkflowStateMachine:
    _TRANSITIONS: dict[tuple[WorkflowStatus, WorkflowStatus], list[str]] = {
        (WorkflowStatus.PENDING, WorkflowStatus.READY): ["dependencies_met"],
        (WorkflowStatus.PENDING, WorkflowStatus.RUNNING): ["dependencies_met_and_assigned"],
        (WorkflowStatus.READY, WorkflowStatus.RUNNING): ["assigned", "started"],
        (WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED): ["success"],
        (WorkflowStatus.RUNNING, WorkflowStatus.FAILED): ["failure"],
        (WorkflowStatus.RUNNING, WorkflowStatus.BLOCKED): ["external_block"],
        (WorkflowStatus.FAILED, WorkflowStatus.READY): ["retry_scheduled"],
        (WorkflowStatus.FAILED, WorkflowStatus.BLOCKED): ["retry_exhausted"],
        (WorkflowStatus.BLOCKED, WorkflowStatus.READY): ["resolved"],
    }

    def __init__(self, graph: TaskGraph) -> None:
        self.graph = graph

    def can_transition(self, node_id: str, target: WorkflowStatus) -> tuple[bool, list[str]]:
        node = self.graph.nodes.get(node_id)
        if node is None:
            return False, [f"Node '{node_id}' not found"]
        current = node.status
        if current == target:
            return True, []
        allowed = self._TRANSITIONS.get((current, target))
        if allowed is None:
            return False, [f"Invalid transition from {current.value} to {target.value}"]
        if target == WorkflowStatus.READY and current == WorkflowStatus.PENDING:
            preds = self.graph.predecessors(node_id)
            if preds and not all(p.status == WorkflowStatus.COMPLETED for p in preds):
                return False, ["Dependencies not met"]
        if target == WorkflowStatus.READY and current == WorkflowStatus.FAILED:
            if node.retry_count >= node.max_retries:
                return False, ["Retry budget exhausted"]
        return True, []

    def transition(
        self, node_id: str, target: WorkflowStatus, reason: str = "", agent_id: str | None = None
    ) -> TransitionResult:
        node = self.graph.nodes.get(node_id)
        if node is None:
            return TransitionResult(success=False, errors=[f"Node '{node_id}' not found"])
        current = node.status
        can, errors = self.can_transition(node_id, target)
        if not can:
            return TransitionResult(success=False, previous_status=current, errors=errors)
        node.status = target
        if agent_id:
            node.agent_id = agent_id
        event = {
            "type": "workflow_state_changed",
            "node_id": node_id,
            "previous_status": current.value,
            "new_status": target.value,
            "reason": reason,
            "agent_id": agent_id,
        }
        if target == WorkflowStatus.FAILED:
            node.retry_count += 1
        return TransitionResult(
            success=True,
            previous_status=current,
            new_status=target,
            events=[event],
        )

    def bulk_transition(self, node_ids: list[str], target: WorkflowStatus, reason: str = "") -> list[TransitionResult]:
        return [self.transition(nid, target, reason) for nid in node_ids]

    def apply_event(self, event: dict[str, Any]) -> TransitionResult:
        node_id = event.get("node_id")
        new_status_str = event.get("new_status")
        reason = event.get("reason", "")
        agent_id = event.get("agent_id")
        if not node_id or not new_status_str:
            return TransitionResult(success=False, errors=["Missing node_id or new_status in event"])
        try:
            target = WorkflowStatus(new_status_str)
        except ValueError:
            return TransitionResult(success=False, errors=[f"Unknown status '{new_status_str}'"])
        return self.transition(node_id, target, reason, agent_id)

    def apply_events(self, events: list[dict[str, Any]]) -> list[TransitionResult]:
        return [self.apply_event(ev) for ev in events]
