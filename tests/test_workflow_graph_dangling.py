"""Regression tests: _find_cycle KeyError on dangling edges.

These tests guard against the bug where validate() detected a dangling
from_id/to_id but still called _find_cycle(), which raised KeyError on
adj[edge.from_id] for non-existent nodes.
"""

from allbrain.workflow.models import TaskEdge, TaskGraph, TaskNode, WorkflowStatus, EdgeType
from allbrain.workflow.graph import DependencyEngine


def _node(nid: str, status: WorkflowStatus = WorkflowStatus.PENDING) -> TaskNode:
    return TaskNode(node_id=nid, task_id=nid, goal="g", status=status, priority=1)


def _depends(frm: str, to: str) -> TaskEdge:
    return TaskEdge(from_id=frm, to_id=to, edge_type=EdgeType.DEPENDS_ON)


class TestDanglingEdges:
    def test_validate_dangling_from_id_no_crash(self):
        graph = TaskGraph(nodes={"a": _node("a")}, edges=[_depends("ghost", "a")])
        result = DependencyEngine().validate(graph)
        assert not result.valid
        assert any("unknown from_id 'ghost'" in e for e in result.errors)
        assert "ghost" in result.dangling_nodes

    def test_validate_dangling_to_id_no_crash(self):
        graph = TaskGraph(nodes={"a": _node("a")}, edges=[_depends("a", "ghost")])
        result = DependencyEngine().validate(graph)
        assert not result.valid
        assert "ghost" in result.dangling_nodes

    def test_is_dag_dangling_edge_does_not_crash(self):
        graph = TaskGraph(nodes={"a": _node("a")}, edges=[_depends("a", "ghost")])
        assert DependencyEngine().is_dag(graph) is True

    def test_topological_sort_dangling_edge_does_not_crash(self):
        graph = TaskGraph(
            nodes={"a": _node("a"), "b": _node("b")},
            edges=[_depends("a", "b"), _depends("a", "ghost")],
        )
        result = DependencyEngine().topological_sort(graph)
        assert "a" in result and "b" in result
        assert "ghost" not in result
