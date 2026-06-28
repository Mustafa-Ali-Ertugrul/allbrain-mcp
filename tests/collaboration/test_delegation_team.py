from __future__ import annotations

from allbrain.collaboration import CollaborationContext, CollaborationManager, DelegationPolicy, DelegationService, TeamBuilder


def test_delegation_flow_and_policy_are_deterministic() -> None:
    service = DelegationService()
    policy = DelegationPolicy(max_depth=2)

    delegation = service.create(task_id="t1", from_agent="planner", to_agent="researcher", reason="needs research")

    assert policy.can_delegate(current_depth=1, from_agent="planner", to_agent="researcher")
    assert not policy.can_delegate(current_depth=2, from_agent="planner", to_agent="researcher")
    assert delegation.to_event_payload()["from_agent"] == "planner"
    assert service.complete_payload(delegation, outcome="done")["status"] == "completed"


def test_collaboration_manager_starts_team_context() -> None:
    team = TeamBuilder().build(
        name="research",
        purpose="answer deeply",
        supervisor="supervisor",
        members=[{"agent_id": "planner", "role": "planner", "capabilities": ["planning"]}],
    )
    context = CollaborationContext(collaboration_id="c1", objective="Research auth", team_name="research", task_id="t1")

    payload = CollaborationManager().start_payload(context, team)

    assert payload["collaboration_id"] == "c1"
    assert payload["team"]["supervisor"] == "supervisor"
