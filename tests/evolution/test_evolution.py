from __future__ import annotations

from allbrain.events import EventType
from allbrain.evolution import (
    ConsensusOptimizer,
    DelegationOptimizer,
    LearningManager,
    LearningMetrics,
    OrganizationalLearning,
    PolicyFeedbackLoop,
    RecommendationEngine,
    SupervisorOptimizer,
    TeamOptimizer,
)
from allbrain.graph import WorkflowGraphBuilder
from allbrain.memory import MemoryBuilder
from allbrain.observability import DashboardDataBuilder
from allbrain.replay import EventReplayEngine
from allbrain.server.app import save_event_impl
from tests.test_sprint12_memory_policy_ui import events, make_context


def seed_learning_history(context) -> None:
    assert save_event_impl(context, type=EventType.COLLABORATION_STARTED.value, payload={"collaboration_id": "c1", "team_name": "research", "objective": "Analyze", "task_id": "t1"}, agent_id="supervisor").ok
    assert save_event_impl(context, type=EventType.DELEGATION_CREATED.value, payload={"delegation_id": "d1", "from_agent": "planner", "to_agent": "researcher", "task_id": "t1", "reason": "research"}, agent_id="planner").ok
    assert save_event_impl(context, type=EventType.DELEGATION_COMPLETED.value, payload={"delegation_id": "d1", "from_agent": "planner", "to_agent": "researcher", "task_id": "t1", "outcome": "done"}, agent_id="researcher").ok
    assert save_event_impl(context, type=EventType.VOTE_CAST.value, payload={"consensus_id": "s1", "agent_id": "planner", "vote": "accept", "weight": 0.7}, agent_id="planner").ok
    assert save_event_impl(context, type=EventType.VOTE_CAST.value, payload={"consensus_id": "s1", "agent_id": "reviewer", "vote": "accept", "weight": 0.3}, agent_id="reviewer").ok
    assert save_event_impl(context, type=EventType.CONSENSUS_REACHED.value, payload={"consensus_id": "s1", "mode": "weighted", "decision": "approve"}, agent_id="supervisor").ok
    assert save_event_impl(context, type=EventType.SUPERVISOR_INTERVENTION.value, payload={"supervisor_id": "supervisor", "task_id": "t1", "action": "approve_completion"}, agent_id="supervisor").ok
    assert save_event_impl(context, type=EventType.COLLABORATION_COMPLETED.value, payload={"collaboration_id": "c1", "team_name": "research", "outcome": "success"}, agent_id="supervisor").ok


def test_optimizers_learn_from_collaboration_history(tmp_path) -> None:
    context = make_context(tmp_path)
    seed_learning_history(context)
    all_events = events(context)

    assert TeamOptimizer().optimize(all_events)[0].success_rate == 1.0
    assert DelegationOptimizer().optimize(all_events)[0]["success_rate"] == 1.0
    assert ConsensusOptimizer().optimize(all_events)[0]["mode"] == "weighted"
    assert SupervisorOptimizer().optimize(all_events)[0]["supervisor_id"] == "supervisor"


def test_learning_manager_recommendation_and_policy_feedback(tmp_path) -> None:
    context = make_context(tmp_path)
    seed_learning_history(context)
    cycle = LearningManager().run_cycle(events(context))
    recommendation = cycle["recommendations"][0]
    policy_update = PolicyFeedbackLoop().propose_update(recommendation)

    assert cycle["learning"]["learning_confidence"] > 0
    assert recommendation["confidence"] > 0
    assert policy_update["recommendation_id"] == recommendation["recommendation_id"]
    assert RecommendationEngine().generate(kind="consensus", subject="weighted", confidence=2, evidence=[], source_metrics={})["confidence"] == 1.0


def test_learning_events_replay_graph_memory_and_observability(tmp_path) -> None:
    context = make_context(tmp_path)
    seed_learning_history(context)
    assert save_event_impl(context, type=EventType.LEARNING_CYCLE_STARTED.value, payload={"cycle_id": "lc1"}).ok
    assert save_event_impl(context, type=EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value, payload={"pattern_id": "pat1", "kind": "successful_team_pattern", "summary": "research team works", "confidence": 0.9}).ok
    assert save_event_impl(context, type=EventType.RECOMMENDATION_GENERATED.value, payload={"recommendation_id": "rec1", "kind": "team", "subject": "research", "confidence": 0.9, "source_metrics": {"success_rate": 1.0}, "supporting_evidence": ["pat1"]}).ok
    assert save_event_impl(context, type=EventType.RECOMMENDATION_APPLIED.value, payload={"recommendation_id": "rec1"}).ok
    assert save_event_impl(context, type=EventType.POLICY_UPDATE_PROPOSED.value, payload={"policy_update_id": "pu1", "recommendation_id": "rec1"}).ok
    assert save_event_impl(context, type=EventType.POLICY_UPDATE_APPROVED.value, payload={"policy_update_id": "pu1", "recommendation_id": "rec1"}).ok
    assert save_event_impl(context, type=EventType.LEARNING_CYCLE_COMPLETED.value, payload={"cycle_id": "lc1"}).ok
    all_events = events(context)

    replay = EventReplayEngine().replay(all_events)["final_state"]
    graph = WorkflowGraphBuilder().build(all_events)
    memory = MemoryBuilder().build(all_events)
    dashboard = DashboardDataBuilder().build(all_events)
    metrics = LearningMetrics().build(all_events)
    learning = OrganizationalLearning().learn(all_events)

    assert replay["organizational_learning"]["cycles"]["lc1"]["status"] == "completed"
    assert replay["recommendations"]["rec1"]["status"] == "applied"
    assert replay["policy_updates"]["pu1"]["status"] == "approved"
    assert "recommendation:rec1" in graph["nodes"]
    assert "policy_update:pu1" in graph["nodes"]
    assert any(edge["edge_type"] in {"recommends", "influences", "improves"} for edge in graph["edges"])
    assert any(item.tags.get("kind") == "successful_team_pattern" for item in memory)
    assert dashboard["learning"]["recommendation_accuracy"] == 1.0
    assert metrics["policy_improvement_rate"] == 1.0
    assert learning["learning_confidence"] > 0
