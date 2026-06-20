from datetime import datetime, timezone

from allbrain.models.schemas import EventRead
from allbrain.orchestrator.metrics import AgentPerformanceReducer


def event(event_id: str, type: str, agent_id: str, payload: dict) -> EventRead:
    return EventRead(
        id=event_id,
        project_id=1,
        session_id=1,
        agent_id=agent_id,
        type=type,
        source="test",
        file_path=None,
        payload=payload,
        task_hint=None,
        importance=None,
        impact_score=None,
        caused_by=None,
        branch=agent_id,
        created_at=datetime.now(timezone.utc),
    )


def test_agent_metrics_aggregate_counts_rates_and_confidence() -> None:
    events = [
        event("1", "task_assigned", "codex", {"task_id": "a", "agent_id": "codex"}),
        event("2", "task_completed", "codex", {"task_id": "a"}),
        event("3", "task_failed", "codex", {"task_id": "b"}),
        event("4", "task_blocked", "claude", {"task_id": "c"}),
    ]

    metrics = AgentPerformanceReducer().reduce(events)

    assert metrics["codex"]["assigned_count"] == 1
    assert metrics["codex"]["success_count"] == 1
    assert metrics["codex"]["failure_count"] == 1
    assert metrics["codex"]["success_rate"] == 0.5
    assert metrics["codex"]["failure_rate"] == 0.5
    assert metrics["codex"]["confidence"] > 0
    assert metrics["claude"]["blocked_count"] == 1
    assert AgentPerformanceReducer().reduce(events) == metrics
