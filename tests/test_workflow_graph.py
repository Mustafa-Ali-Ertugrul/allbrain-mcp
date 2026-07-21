"""Tests for workflow/graph.py uncovered branches - DependencyEngine."""

from allbrain.domains.collaboration.workflow.graph import DependencyEngine
from allbrain.domains.collaboration.workflow.models import TaskEdge, TaskGraph, TaskNode, WorkflowStatus


def _graph(*nodes: TaskNode) -> TaskGraph:
    g = TaskGraph()
    for n in nodes:
        g.add_node(n)
    return g


def _node(nid: str, status: WorkflowStatus = WorkflowStatus.PENDING, priority: int = 3) -> TaskNode:
    return TaskNode(node_id=nid, task_id=nid, goal="test", status=status, priority=priority)


class TestDependencyEngineValidate:
    def test_empty_graph(self):
        engine = DependencyEngine()
        result = engine.validate(TaskGraph())
        assert not result.valid
        assert any("no nodes" in e for e in result.errors)

    def test_self_loop(self):
        g = _graph(_node("n1"))
        g.add_edge(TaskEdge(from_id="n1", to_id="n1"))
        result = DependencyEngine().validate(g)
        assert not result.valid
        assert any("Self-loop" in e for e in result.errors)
        assert len(result.cycles) >= 1

    def test_cycle_detected(self):
        g = _graph(_node("n1"), _node("n2"))
        g.add_edge(TaskEdge(from_id="n1", to_id="n2"))
        g.add_edge(TaskEdge(from_id="n2", to_id="n1"))
        result = DependencyEngine().validate(g)
        assert not result.valid
        assert any("Cycle" in e for e in result.errors)

    def test_valid_dag(self):
        g = _graph(_node("n1"), _node("n2"))
        g.add_edge(TaskEdge(from_id="n1", to_id="n2"))
        result = DependencyEngine().validate(g)
        assert result.valid


class TestDependencyEngineBlockingReason:
    def test_node_not_found(self):
        g = _graph()
        reason = DependencyEngine().blocking_reason(g, "nonexistent")
        assert reason == "Node not found"

    def test_completed_node_not_blocked(self):
        g = _graph(_node("n1", WorkflowStatus.COMPLETED))
        assert DependencyEngine().blocking_reason(g, "n1") is None

    def test_running_node_not_blocked(self):
        g = _graph(_node("n1", WorkflowStatus.RUNNING))
        assert DependencyEngine().blocking_reason(g, "n1") is None

    def test_no_predecessors_not_blocked(self):
        g = _graph(_node("n1", WorkflowStatus.PENDING))
        assert DependencyEngine().blocking_reason(g, "n1") is None

    def test_failed_predecessor(self):
        g = _graph(
            _node("n1", WorkflowStatus.COMPLETED),
            _node("n2", WorkflowStatus.FAILED),
            _node("n3", WorkflowStatus.PENDING),
        )
        g.add_edge(TaskEdge(from_id="n1", to_id="n3"))
        g.add_edge(TaskEdge(from_id="n2", to_id="n3"))
        reason = DependencyEngine().blocking_reason(g, "n3")
        assert reason is not None
        assert "failed" in reason

    def test_blocked_predecessor(self):
        g = _graph(
            _node("n1", WorkflowStatus.COMPLETED),
            _node("n2", WorkflowStatus.BLOCKED),
            _node("n3", WorkflowStatus.PENDING),
        )
        g.add_edge(TaskEdge(from_id="n1", to_id="n3"))
        g.add_edge(TaskEdge(from_id="n2", to_id="n3"))
        reason = DependencyEngine().blocking_reason(g, "n3")
        assert reason and "blocked" in reason

    def test_pending_predecessor(self):
        g = _graph(_node("n1", WorkflowStatus.PENDING), _node("n2", WorkflowStatus.PENDING))
        g.add_edge(TaskEdge(from_id="n1", to_id="n2"))
        reason = DependencyEngine().blocking_reason(g, "n2")
        assert reason and "pending" in reason


class TestDependencyEngineCriticalPath:
    def test_empty_graph(self):
        g = _graph()
        assert DependencyEngine().critical_path(g) == []

    def test_single_node(self):
        g = _graph(_node("n1", priority=5))
        path = DependencyEngine().critical_path(g)
        assert path == ["n1"]

    def test_linear_path(self):
        g = _graph(_node("n1", priority=3), _node("n2", priority=5))
        g.add_edge(TaskEdge(from_id="n1", to_id="n2"))
        path = DependencyEngine().critical_path(g)
        assert path == ["n1", "n2"]

    def test_cycle_returns_empty_critical_path(self):
        g = _graph(_node("n1"), _node("n2"))
        g.add_edge(TaskEdge(from_id="n1", to_id="n2"))
        g.add_edge(TaskEdge(from_id="n2", to_id="n1"))
        assert DependencyEngine().critical_path(g) == []

    def test_topological_sort_with_cycle(self):
        g = _graph(_node("n1"), _node("n2"))
        g.add_edge(TaskEdge(from_id="n1", to_id="n2"))
        g.add_edge(TaskEdge(from_id="n2", to_id="n1"))
        assert DependencyEngine().topological_sort(g) == []
