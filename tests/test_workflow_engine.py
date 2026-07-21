from __future__ import annotations

from allbrain.domains.collaboration.workflow.aggregator import ResultAggregator
from allbrain.domains.collaboration.workflow.engine import WorkflowEngine
from allbrain.domains.collaboration.workflow.graph import DependencyEngine
from allbrain.domains.collaboration.workflow.models import (
    AggregationStrategy,
    EdgeType,
    SubtaskResult,
    TaskEdge,
    TaskGraph,
    TaskNode,
    WorkflowStatus,
)
from allbrain.domains.collaboration.workflow.recovery import RecoveryManager
from allbrain.domains.collaboration.workflow.scheduler import SubtaskScheduler
from allbrain.domains.collaboration.workflow.state_machine import WorkflowStateMachine


def make_graph(*, ready_roots: bool = True) -> TaskGraph:
    graph = TaskGraph(root_task_id="oauth")
    nodes = [
        TaskNode(node_id="n1", task_id="oauth", goal="Design API", kind="design", priority=5, depth=0),
        TaskNode(node_id="n2", task_id="oauth", goal="Implement Backend", kind="implementation", priority=4, depth=1),
        TaskNode(node_id="n3", task_id="oauth", goal="Write Tests", kind="testing", priority=3, depth=1),
        TaskNode(node_id="n4", task_id="oauth", goal="Security Review", kind="review", priority=5, depth=2),
    ]
    for n in nodes:
        graph.add_node(n)
    edges = [
        TaskEdge("n1", "n2", EdgeType.DEPENDS_ON),
        TaskEdge("n1", "n3", EdgeType.DEPENDS_ON),
        TaskEdge("n2", "n4", EdgeType.DEPENDS_ON),
        TaskEdge("n3", "n4", EdgeType.DEPENDS_ON),
    ]
    for e in edges:
        graph.add_edge(e)
    if ready_roots:
        for n in graph.nodes.values():
            if not graph.predecessors(n.node_id):
                n.status = WorkflowStatus.READY
    return graph


def test_task_graph_predecessors_and_successors() -> None:
    graph = make_graph()
    assert len(graph.predecessors("n2")) == 1
    assert graph.predecessors("n2")[0].node_id == "n1"
    assert len(graph.successors("n1")) == 2
    succ_ids = {s.node_id for s in graph.successors("n1")}
    assert succ_ids == {"n2", "n3"}


def test_dependency_engine_validates_dag() -> None:
    engine = DependencyEngine()
    graph = make_graph()
    result = engine.validate(graph)
    assert result.valid
    assert not result.cycles


def test_dependency_engine_detects_cycle() -> None:
    engine = DependencyEngine()
    graph = make_graph()
    graph.add_edge(TaskEdge("n4", "n1", EdgeType.DEPENDS_ON))
    result = engine.validate(graph)
    assert not result.valid
    assert result.cycles
    assert any("n1" in cycle and "n4" in cycle for cycle in result.cycles)


def test_dependency_engine_ready_set() -> None:
    engine = DependencyEngine()
    graph = make_graph()
    ready = engine.ready_set(graph)
    assert len(ready) == 1
    assert ready[0].node_id == "n1"


def test_dependency_engine_ready_set_after_completion() -> None:
    engine = DependencyEngine()
    graph = make_graph()
    graph.nodes["n1"].status = WorkflowStatus.COMPLETED
    ready = engine.ready_set(graph)
    assert len(ready) == 2
    assert {n.node_id for n in ready} == {"n2", "n3"}


def test_dependency_engine_blocking_reason() -> None:
    engine = DependencyEngine()
    graph = make_graph()
    graph.nodes["n1"].status = WorkflowStatus.FAILED
    reason = engine.blocking_reason(graph, "n2")
    assert reason and "failed" in reason.lower()


def test_dependency_engine_topological_sort() -> None:
    engine = DependencyEngine()
    graph = make_graph()
    topo = engine.topological_sort(graph)
    assert topo.index("n1") < topo.index("n2")
    assert topo.index("n1") < topo.index("n3")
    assert topo.index("n2") < topo.index("n4")
    assert topo.index("n3") < topo.index("n4")


def test_dependency_engine_is_dag() -> None:
    engine = DependencyEngine()
    assert engine.is_dag(make_graph())
    bad = make_graph()
    bad.add_edge(TaskEdge("n4", "n1", EdgeType.DEPENDS_ON))
    assert not engine.is_dag(bad)


def test_state_machine_pending_to_ready() -> None:
    graph = make_graph(ready_roots=False)
    sm = WorkflowStateMachine(graph)
    result = sm.transition("n1", WorkflowStatus.READY, reason="dependencies_met")
    assert result.success
    assert graph.nodes["n1"].status == WorkflowStatus.READY


def test_state_machine_ready_to_running() -> None:
    graph = make_graph()
    sm = WorkflowStateMachine(graph)
    result = sm.transition("n1", WorkflowStatus.RUNNING, agent_id="architect")
    assert result.success
    assert graph.nodes["n1"].status == WorkflowStatus.RUNNING
    assert graph.nodes["n1"].agent_id == "architect"


def test_state_machine_running_to_completed() -> None:
    graph = make_graph()
    sm = WorkflowStateMachine(graph)
    sm.transition("n1", WorkflowStatus.RUNNING)
    result = sm.transition("n1", WorkflowStatus.COMPLETED)
    assert result.success
    assert graph.nodes["n1"].status == WorkflowStatus.COMPLETED


def test_state_machine_running_to_failed_to_retry() -> None:
    graph = make_graph()
    sm = WorkflowStateMachine(graph)
    sm.transition("n1", WorkflowStatus.RUNNING)
    result = sm.transition("n1", WorkflowStatus.FAILED, reason="test_failure")
    assert result.success
    assert graph.nodes["n1"].status == WorkflowStatus.FAILED
    assert graph.nodes["n1"].retry_count == 1

    result2 = sm.transition("n1", WorkflowStatus.READY, reason="retry")
    assert result2.success
    assert graph.nodes["n1"].status == WorkflowStatus.READY


def test_state_machine_blocks_retry_when_exhausted() -> None:
    graph = make_graph()
    sm = WorkflowStateMachine(graph)
    graph.nodes["n1"].retry_count = 3
    graph.nodes["n1"].max_retries = 3
    sm.transition("n1", WorkflowStatus.RUNNING)
    sm.transition("n1", WorkflowStatus.FAILED)
    can, errors = sm.can_transition("n1", WorkflowStatus.READY)
    assert not can
    assert any("budget" in e.lower() for e in errors)


def test_state_machine_invalid_transition() -> None:
    graph = make_graph()
    sm = WorkflowStateMachine(graph)
    result = sm.transition("n1", WorkflowStatus.FAILED)
    assert not result.success


def test_scheduler_next_subtasks() -> None:
    graph = make_graph()
    scheduler = SubtaskScheduler()
    metrics = {
        "architect": {
            "agent_id": "architect",
            "success_count": 10,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 1.0,
            "failure_rate": 0.0,
            "blocked_rate": 0.0,
            "confidence": 0.8,
        },
    }
    assignments = scheduler.next_subtasks(
        graph=graph,
        candidate_agents=["architect"],
        metrics=metrics,
        max_parallel=3,
    )
    assert len(assignments) == 1
    assert assignments[0].node_id == "n1"
    assert assignments[0].agent_id == "architect"


def test_aggregator_concat() -> None:
    agg = ResultAggregator()
    results = [
        SubtaskResult("n1", "architect", "API Design Doc"),
        SubtaskResult("n2", "builder", "Backend Code"),
    ]
    result = agg.aggregate(parent_task_id="oauth", subtask_results=results, strategy=AggregationStrategy.CONCAT)
    assert len(result.outputs) == 2
    assert "API Design Doc" in result.outputs[0]


def test_aggregator_merge() -> None:
    agg = ResultAggregator()
    results = [
        SubtaskResult("n1", "a", "out1", metadata={"key": "val1"}),
        SubtaskResult("n2", "b", "out2", metadata={"key": "val2"}),
    ]
    result = agg.aggregate(parent_task_id="oauth", subtask_results=results, strategy=AggregationStrategy.MERGE)
    assert len(result.conflicts) == 1
    assert result.conflicts[0]["key"] == "key"


def test_aggregator_vote() -> None:
    agg = ResultAggregator()
    results = [
        SubtaskResult("n1", "a", "approve"),
        SubtaskResult("n2", "b", "approve"),
        SubtaskResult("n3", "c", "reject"),
    ]
    result = agg.aggregate(parent_task_id="oauth", subtask_results=results, strategy=AggregationStrategy.VOTE)
    assert result.outputs == ["approve"]
    assert result.metadata["winner_count"] == 2
    assert result.metadata["total_votes"] == 3


def test_aggregator_empty() -> None:
    agg = ResultAggregator()
    result = agg.aggregate(parent_task_id="oauth", subtask_results=[])
    assert result.outputs == []
    assert result.metadata["count"] == 0


def test_recovery_retry() -> None:
    graph = make_graph()
    graph.nodes["n1"].status = WorkflowStatus.RUNNING
    rm = RecoveryManager(max_retries=3)
    decision = rm.handle_failure(graph=graph, node_id="n1", error="timeout")
    assert decision.action == "retry"
    assert graph.nodes["n1"].status == WorkflowStatus.READY
    assert decision.delay_seconds > 0


def test_recovery_block_and_cascade() -> None:
    graph = make_graph()
    graph.nodes["n1"].status = WorkflowStatus.RUNNING
    graph.nodes["n1"].retry_count = 3
    graph.nodes["n1"].max_retries = 3
    rm = RecoveryManager(max_retries=3)
    decision = rm.handle_failure(graph=graph, node_id="n1", error="fatal")
    assert decision.action == "block"
    assert graph.nodes["n1"].status == WorkflowStatus.BLOCKED
    assert "n2" in decision.affected_nodes
    assert "n3" in decision.affected_nodes
    assert "n4" in decision.affected_nodes
    assert graph.nodes["n4"].status == WorkflowStatus.BLOCKED


def test_recovery_resume_workflow() -> None:
    graph = make_graph(ready_roots=False)
    graph.nodes["n1"].status = WorkflowStatus.COMPLETED
    graph.nodes["n1"].result = SubtaskResult("n1", "architect", "design done")
    rm = RecoveryManager()
    rm.resume_workflow(
        graph=graph,
        completed_results={"n1": SubtaskResult("n1", "architect", "design done")},
    )
    assert graph.nodes["n1"].status == WorkflowStatus.COMPLETED
    ready = DependencyEngine().ready_set(graph)
    assert {n.node_id for n in ready} == {"n2", "n3"}


def test_workflow_engine_create_workflow() -> None:
    engine = WorkflowEngine()
    graph = engine.create_workflow(
        task_id="oauth",
        goal="Implement OAuth Login",
        subtasks=[
            {"node_id": "n_design", "goal": "Design API", "kind": "design", "priority": 5},
            {"node_id": "n_impl", "goal": "Implement Backend", "kind": "implementation", "priority": 4},
            {"node_id": "n_test", "goal": "Write Tests", "kind": "testing", "priority": 3},
            {"node_id": "n_review", "goal": "Security Review", "kind": "review", "priority": 5},
        ],
        edges=[
            {"from": "n_design", "to": "n_impl"},
            {"from": "n_design", "to": "n_test"},
            {"from": "n_impl", "to": "n_review"},
            {"from": "n_test", "to": "n_review"},
        ],
    )
    assert len(graph.nodes) == 4
    assert DependencyEngine().is_dag(graph)


def test_workflow_engine_create_workflow_detects_cycle() -> None:
    engine = WorkflowEngine()
    try:
        engine.create_workflow(
            task_id="oauth",
            goal="Implement OAuth Login",
            subtasks=[
                {"goal": "A", "kind": "implementation", "priority": 3, "node_id": "n_a"},
                {"goal": "B", "kind": "implementation", "priority": 3, "node_id": "n_b"},
            ],
            edges=[
                {"from": "n_a", "to": "n_b"},
                {"from": "n_b", "to": "n_a"},
            ],
        )
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "cycle" in str(exc).lower() or "invalid" in str(exc).lower()


def test_workflow_engine_step_schedules_ready_nodes() -> None:
    engine = WorkflowEngine()
    graph = make_graph()
    metrics = {
        "architect": {
            "agent_id": "architect",
            "success_count": 10,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 1.0,
            "failure_rate": 0.0,
            "blocked_rate": 0.0,
            "confidence": 0.8,
        },
        "builder": {
            "agent_id": "builder",
            "success_count": 8,
            "failure_count": 2,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 0.8,
            "failure_rate": 0.2,
            "blocked_rate": 0.0,
            "confidence": 0.7,
        },
    }
    step_result = engine.step(
        graph,
        candidate_agents=["architect", "builder"],
        metrics=metrics,
        max_parallel=3,
    )
    assert len(step_result.assignments) == 1
    assert step_result.assignments[0]["node_id"] == "n1"
    assert step_result.events
    assert graph.nodes["n1"].status == WorkflowStatus.RUNNING


def test_workflow_engine_step_completes_and_aggregates() -> None:
    engine = WorkflowEngine()
    graph = make_graph()
    metrics = {
        "architect": {
            "agent_id": "architect",
            "success_count": 10,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 1.0,
            "failure_rate": 0.0,
            "blocked_rate": 0.0,
            "confidence": 0.8,
        },
    }
    # Step 1: schedule n1 to RUNNING
    engine.step(
        graph,
        candidate_agents=["architect"],
        metrics=metrics,
    )
    assert graph.nodes["n1"].status == WorkflowStatus.RUNNING

    # Step 2: complete n1
    engine.step(
        graph,
        candidate_agents=["architect"],
        metrics=metrics,
        completions={"n1": SubtaskResult("n1", "architect", "API Design Doc")},
    )
    assert graph.nodes["n1"].status == WorkflowStatus.COMPLETED
    assert {n.node_id for n in graph.nodes.values() if n.status == WorkflowStatus.RUNNING} == {"n2", "n3"}


def test_workflow_engine_step_failure_recovery() -> None:
    engine = WorkflowEngine()
    graph = make_graph()
    # Simulate n1 running and failing once
    graph.nodes["n1"].status = WorkflowStatus.RUNNING
    metrics = {
        "architect": {
            "agent_id": "architect",
            "success_count": 10,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 1.0,
            "confidence": 0.8,
        },
    }
    step_result = engine.step(
        graph,
        candidate_agents=["architect"],
        metrics=metrics,
        failures={"n1": "network timeout"},
    )
    assert any(r["action"] == "retry" for r in step_result.recovered)
    assert graph.nodes["n1"].status == WorkflowStatus.READY
    # n1 should not have been re-scheduled in the same step
    assert graph.nodes["n1"].status != WorkflowStatus.RUNNING


def test_workflow_engine_run_full_dag() -> None:
    engine = WorkflowEngine()
    graph = make_graph()
    metrics = {
        "architect": {
            "agent_id": "architect",
            "success_count": 10,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 1.0,
            "confidence": 0.8,
        },
        "builder": {
            "agent_id": "builder",
            "success_count": 8,
            "failure_count": 2,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 0.8,
            "confidence": 0.7,
        },
        "tester": {
            "agent_id": "tester",
            "success_count": 9,
            "failure_count": 1,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 0.9,
            "confidence": 0.75,
        },
        "reviewer": {
            "agent_id": "reviewer",
            "success_count": 10,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 1.0,
            "confidence": 0.85,
        },
    }

    # Simulate step-by-step with manual completions
    max_iterations = 30
    for _ in range(max_iterations):
        # Complete any running nodes
        completions = {}
        for nid, node in graph.nodes.items():
            if node.status == WorkflowStatus.RUNNING and node.agent_id:
                completions[nid] = SubtaskResult(nid, node.agent_id, f"output from {node.agent_id}")
        result = engine.step(
            graph,
            candidate_agents=["architect", "builder", "tester", "reviewer"],
            metrics=metrics,
            completions=completions,
            max_parallel=4,
        )
        if result.is_done:
            break

    assert graph.nodes["n1"].status == WorkflowStatus.COMPLETED
    assert graph.nodes["n2"].status == WorkflowStatus.COMPLETED
    assert graph.nodes["n3"].status == WorkflowStatus.COMPLETED
    assert graph.nodes["n4"].status == WorkflowStatus.COMPLETED


def test_workflow_serialization_roundtrip() -> None:
    graph = make_graph()
    graph.nodes["n1"].status = WorkflowStatus.COMPLETED
    graph.nodes["n1"].result = SubtaskResult("n1", "architect", "design doc", artifacts=["api.yml"])
    data = graph.to_dict()
    restored = TaskGraph.from_dict(data)
    assert len(restored.nodes) == len(graph.nodes)
    assert restored.nodes["n1"].status == WorkflowStatus.COMPLETED
    assert restored.nodes["n1"].result.output == "design doc"


def test_workflow_engine_only_failed_node_retries() -> None:
    engine = WorkflowEngine()
    graph = make_graph()
    # Simulate n1 running and failing once
    graph.nodes["n1"].status = WorkflowStatus.RUNNING
    metrics = {
        "architect": {
            "agent_id": "architect",
            "success_count": 10,
            "failure_count": 0,
            "blocked_count": 0,
            "assigned_count": 10,
            "total_tasks": 10,
            "success_rate": 1.0,
            "confidence": 0.8,
        },
    }
    step_result = engine.step(
        graph,
        candidate_agents=["architect"],
        metrics=metrics,
        failures={"n1": "flaky test"},
    )
    # n1 should be READY for retry, others should still be PENDING
    assert graph.nodes["n1"].status == WorkflowStatus.READY
    assert graph.nodes["n2"].status == WorkflowStatus.PENDING
    assert graph.nodes["n3"].status == WorkflowStatus.PENDING
    assert graph.nodes["n4"].status == WorkflowStatus.PENDING
    # The failure event should only mention n1
    fail_events = [e for e in step_result.events if e.get("type") == "subtask_failed"]
    assert len(fail_events) == 1
    assert fail_events[0]["node_id"] == "n1"
