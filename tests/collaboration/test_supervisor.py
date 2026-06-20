from __future__ import annotations

from allbrain.collaboration import Supervisor


def test_supervisor_assign_intervene_and_approve() -> None:
    supervisor = Supervisor("lead")

    assert supervisor.assign(task_id="t1", agent_id="planner", role="planner")["action"] == "assign"
    assert supervisor.intervene(task_id="t1", reason="conflict")["action"] == "resolve_conflict"
    assert supervisor.approve_completion(task_id="t1")["action"] == "approve_completion"
