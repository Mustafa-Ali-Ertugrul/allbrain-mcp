from __future__ import annotations

from allbrain.domains.analysis.graph import WorkflowGraphBuilder
from allbrain.domains.memory.memory import MemoryBuilder
from allbrain.domains.memory.observability import DashboardDataBuilder
from allbrain.domains.memory.replay import EventReplayEngine
from allbrain.events import EventType
from allbrain.server.tools.events import save_event_impl
from tests.test_sprint12_memory_policy_ui import events, make_context


def seed_collaboration(context) -> None:
    assert save_event_impl(
        context,
        type=EventType.COLLABORATION_STARTED.value,
        payload={"collaboration_id": "c1", "objective": "Review auth", "team_name": "review-team", "task_id": "t1"},
        agent_id="supervisor",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.DELEGATION_CREATED.value,
        payload={
            "delegation_id": "d1",
            "task_id": "t1",
            "from_agent": "planner",
            "to_agent": "reviewer",
            "reason": "security",
        },
        agent_id="planner",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.NEGOTIATION_STARTED.value,
        payload={"negotiation_id": "n1", "participants": ["planner", "reviewer"]},
        agent_id="planner",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.PROPOSAL_CREATED.value,
        payload={"negotiation_id": "n1", "proposal_id": "p1", "agent_id": "planner", "content": "Plan A"},
        agent_id="planner",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.PROPOSAL_REJECTED.value,
        payload={"negotiation_id": "n1", "proposal_id": "p1", "agent_id": "reviewer"},
        agent_id="reviewer",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.PROPOSAL_CREATED.value,
        payload={"negotiation_id": "n1", "proposal_id": "p2", "agent_id": "reviewer", "content": "Plan B"},
        agent_id="reviewer",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.PROPOSAL_ACCEPTED.value,
        payload={"negotiation_id": "n1", "proposal_id": "p2", "agent_id": "planner"},
        agent_id="planner",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.VOTE_CAST.value,
        payload={"consensus_id": "s1", "agent_id": "planner", "vote": "accept", "weight": 1.0},
        agent_id="planner",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.VOTE_CAST.value,
        payload={"consensus_id": "s1", "agent_id": "reviewer", "vote": "accept", "weight": 1.0},
        agent_id="reviewer",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.CONSENSUS_REACHED.value,
        payload={"consensus_id": "s1", "decision": "approve"},
        agent_id="supervisor",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.SUPERVISOR_INTERVENTION.value,
        payload={"supervisor_id": "supervisor", "task_id": "t1", "action": "approve_completion", "reason": "consensus"},
        agent_id="supervisor",
    ).ok
    assert save_event_impl(
        context,
        type=EventType.DELEGATION_COMPLETED.value,
        payload={
            "delegation_id": "d1",
            "task_id": "t1",
            "from_agent": "planner",
            "to_agent": "reviewer",
            "outcome": "reviewed",
        },
        agent_id="reviewer",
    ).ok
    assert save_event_impl(
        context, type=EventType.NEGOTIATION_COMPLETED.value, payload={"negotiation_id": "n1"}, agent_id="supervisor"
    ).ok
    assert save_event_impl(
        context,
        type=EventType.COLLABORATION_COMPLETED.value,
        payload={"collaboration_id": "c1", "team_name": "review-team", "outcome": "approved"},
        agent_id="supervisor",
    ).ok


def test_collaboration_replay_graph_memory_and_metrics(tmp_path) -> None:
    context = make_context(tmp_path)
    seed_collaboration(context)
    all_events = events(context)

    replay = EventReplayEngine().replay(all_events)
    graph = WorkflowGraphBuilder().build(all_events)
    memory = MemoryBuilder().build(all_events)
    dashboard = DashboardDataBuilder().build(all_events)

    assert replay["final_state"]["collaboration"]["collaborations"]["c1"]["status"] == "success"
    assert "delegation:d1" in graph["nodes"]
    assert "proposal:p2" in graph["nodes"]
    assert any(edge["edge_type"] == "voted_for" for edge in graph["edges"])
    assert any(item.tags.get("kind") == "collaboration" for item in memory)
    assert dashboard["collaboration"]["delegation_count"] == 1
    assert dashboard["collaboration"]["delegation_success_rate"] == 1.0
    assert dashboard["collaboration"]["negotiation_success_rate"] == 1.0
    assert dashboard["collaboration"]["consensus_participation"] == {"planner": 1, "reviewer": 1}
