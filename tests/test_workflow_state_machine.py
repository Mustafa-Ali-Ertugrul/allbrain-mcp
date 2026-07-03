"""Tests for workflow/state_machine.py - WorkflowStateMachine."""

from allbrain.workflow.models import TaskGraph, TaskNode, WorkflowStatus
from allbrain.workflow.state_machine import WorkflowStateMachine


def _graph_with_node(
    status: WorkflowStatus = WorkflowStatus.PENDING, retry_count: int = 0, max_retries: int = 3
) -> TaskGraph:
    g = TaskGraph()
    g.add_node(
        TaskNode(
            node_id="n1",
            task_id="n1",
            goal="test",
            status=status,
            retry_count=retry_count,
            max_retries=max_retries,
        )
    )
    return g


class TestWorkflowStateMachine:
    def test_can_transition_pending_to_ready(self):
        g = _graph_with_node(WorkflowStatus.PENDING)
        sm = WorkflowStateMachine(g)
        ok, _ = sm.can_transition("n1", WorkflowStatus.READY)
        assert ok

    def test_cannot_transition_pending_to_completed(self):
        g = _graph_with_node(WorkflowStatus.PENDING)
        sm = WorkflowStateMachine(g)
        ok, errors = sm.can_transition("n1", WorkflowStatus.COMPLETED)
        assert not ok
        assert any("Invalid transition" in e for e in errors)

    def test_cannot_transition_nonexistent_node(self):
        g = _graph_with_node()
        sm = WorkflowStateMachine(g)
        ok, errors = sm.can_transition("nonexistent", WorkflowStatus.READY)
        assert not ok
        assert any("not found" in e for e in errors)

    def test_same_status_transition(self):
        g = _graph_with_node(WorkflowStatus.PENDING)
        sm = WorkflowStateMachine(g)
        ok, _ = sm.can_transition("n1", WorkflowStatus.PENDING)
        assert ok

    def test_transition_success(self):
        g = _graph_with_node(WorkflowStatus.READY)
        sm = WorkflowStateMachine(g)
        result = sm.transition("n1", WorkflowStatus.RUNNING, reason="assigned", agent_id="agent1")
        assert result.success
        assert result.previous_status == WorkflowStatus.READY
        assert result.new_status == WorkflowStatus.RUNNING
        assert g.nodes["n1"].status == WorkflowStatus.RUNNING
        assert g.nodes["n1"].agent_id == "agent1"

    def test_transition_nonexistent_node(self):
        g = _graph_with_node()
        sm = WorkflowStateMachine(g)
        result = sm.transition("nonexistent", WorkflowStatus.READY)
        assert not result.success

    def test_transition_invalid_returns_error(self):
        g = _graph_with_node(WorkflowStatus.PENDING)
        sm = WorkflowStateMachine(g)
        result = sm.transition("n1", WorkflowStatus.COMPLETED)
        assert not result.success

    def test_failure_increments_retry(self):
        g = _graph_with_node(WorkflowStatus.RUNNING)
        sm = WorkflowStateMachine(g)
        sm.transition("n1", WorkflowStatus.FAILED)
        assert g.nodes["n1"].retry_count == 1

    def test_bulk_transition(self):
        g = TaskGraph()
        g.add_node(TaskNode(node_id="n1", task_id="n1", goal="test", status=WorkflowStatus.READY))
        g.add_node(TaskNode(node_id="n2", task_id="n2", goal="test", status=WorkflowStatus.READY))
        sm = WorkflowStateMachine(g)
        results = sm.bulk_transition(["n1", "n2"], WorkflowStatus.RUNNING, reason="start")
        assert all(r.success for r in results)
        assert all(n.status == WorkflowStatus.RUNNING for n in g.nodes.values())

    def test_apply_event(self):
        g = _graph_with_node(WorkflowStatus.PENDING)
        sm = WorkflowStateMachine(g)
        event = {"node_id": "n1", "new_status": "ready", "reason": "dep_met", "agent_id": "a1"}
        result = sm.apply_event(event)
        assert result.success

    def test_apply_event_missing_fields(self):
        g = _graph_with_node()
        sm = WorkflowStateMachine(g)
        result = sm.apply_event({"node_id": "n1"})
        assert not result.success

    def test_apply_event_bad_status(self):
        g = _graph_with_node()
        sm = WorkflowStateMachine(g)
        result = sm.apply_event({"node_id": "n1", "new_status": "invalid_status"})
        assert not result.success

    def test_apply_events_batch(self):
        g = TaskGraph()
        g.add_node(TaskNode(node_id="n1", task_id="n1", goal="test", status=WorkflowStatus.READY))
        g.add_node(TaskNode(node_id="n2", task_id="n2", goal="test", status=WorkflowStatus.READY))
        sm = WorkflowStateMachine(g)
        events = [
            {"node_id": "n1", "new_status": "running", "reason": "start"},
            {"node_id": "n2", "new_status": "running", "reason": "start"},
        ]
        results = sm.apply_events(events)
        assert all(r.success for r in results)
