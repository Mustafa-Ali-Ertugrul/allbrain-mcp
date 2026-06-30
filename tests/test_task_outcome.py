from datetime import UTC, datetime, timedelta, timezone

from allbrain.models.schemas import EventRead
from allbrain.orchestrator.metrics import TaskOutcomeReducer


def event(event_id: str, type: str, task_id: str, created_at: datetime) -> EventRead:
    return EventRead(
        id=event_id,
        project_id=1,
        session_id=1,
        agent_id="codex",
        type=type,
        source="test",
        file_path=None,
        payload={"task_id": task_id, "from_agent": "codex", "to_agent": "claude"},
        task_hint=None,
        importance=None,
        impact_score=None,
        caused_by=None,
        branch="codex",
        created_at=created_at,
    )


def test_task_outcome_tracks_duration_agent_changes_and_terminal_state() -> None:
    started = datetime(2026, 6, 18, tzinfo=UTC)
    events = [
        event("1", "task_started", "task_a", started),
        event("2", "handoff_created", "task_a", started + timedelta(seconds=2)),
        event("3", "task_failed", "task_a", started + timedelta(seconds=5)),
    ]

    outcomes = TaskOutcomeReducer().reduce(events)

    assert outcomes["task_a"]["status"] == "failed"
    assert outcomes["task_a"]["duration"] == 5
    assert outcomes["task_a"]["retry_count"] == 1
    assert outcomes["task_a"]["agent_changes"] == 1
