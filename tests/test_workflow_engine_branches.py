"""Deep coverage: workflow/engine.py uncovered branches."""

from allbrain.workflow.engine import WorkflowEngine
from allbrain.workflow.models import EdgeType, SubtaskResult, TaskEdge, TaskGraph, TaskNode, WorkflowStatus


def _node(nid, status=WorkflowStatus.PENDING):
    return TaskNode(node_id=nid, task_id=nid, goal="g", status=status, priority=1)


def _one_node_graph(status=WorkflowStatus.PENDING):
    return TaskGraph(nodes={"a": _node("a", status)}, edges=[])


def _two_node_graph():
    return TaskGraph(
        nodes={"a": _node("a", WorkflowStatus.PENDING), "b": _node("b", WorkflowStatus.PENDING)},
        edges=[TaskEdge(from_id="a", to_id="b", edge_type=EdgeType.DEPENDS_ON)],
    )


def test_step_skip_non_running_on_failure():
    """L117 branch: failure for non-RUNNING node is skipped."""
    graph = _one_node_graph(WorkflowStatus.PENDING)
    engine = WorkflowEngine()
    result = engine.step(graph, candidate_agents=["agent1"], metrics={}, failures={"a": "error"})
    assert "a" not in result.failed


def test_step_cascade_block_on_failure():
    """L135-136: failure with block action cascades to affected_nodes."""
    graph = _two_node_graph()
    graph.nodes["a"].status = WorkflowStatus.RUNNING
    engine = WorkflowEngine()
    result = engine.step(graph, candidate_agents=["agent1"], metrics={}, failures={"a": "some_error"})
    assert "a" in result.failed


def test_step_skip_missing_node_on_completion():
    """L145 branch: completion for non-existent node is skipped."""
    graph = _one_node_graph()
    engine = WorkflowEngine()
    result = engine.step(
        graph, candidate_agents=["agent1"], metrics={},
        completions={"nonexistent": SubtaskResult(node_id="n", agent_id="a", output="")},
    )
    assert "nonexistent" not in result.completed


def test_step_completion_non_running_skips_transition():
    """L148 branch: completion for non-RUNNING node skips transition."""
    graph = _one_node_graph(WorkflowStatus.PENDING)
    engine = WorkflowEngine()
    result = engine.step(
        graph, candidate_agents=["agent1"], metrics={},
        completions={"a": SubtaskResult(node_id="a", agent_id="a", output="")},
    )
    assert "a" not in result.completed


def test_run_all_failed_or_blocked():
    """L245-253: run() detects all failed/blocked."""
    graph = _one_node_graph(WorkflowStatus.FAILED)
    engine = WorkflowEngine()
    result = engine.run(graph, candidate_agents=["agent1"], metrics={}, max_parallel=1, max_steps=1)
    assert not result.success
    assert result.error == "All nodes failed or blocked"


def test_run_exceeds_max_steps():
    """L256-260: run() exceeds max_steps."""
    graph = _two_node_graph()
    engine = WorkflowEngine()
    result = engine.run(graph, candidate_agents=["agent1"], metrics={}, max_parallel=1, max_steps=2)
    assert not result.success
    assert "max_steps" in (result.error or "")


def test_resume_method():
    """L273-279: resume() calls run() after recovery."""
    graph = _one_node_graph()
    engine = WorkflowEngine()
    result = engine.resume(graph, completed_results={}, candidate_agents=["agent1"], metrics={})
    assert result is not None
