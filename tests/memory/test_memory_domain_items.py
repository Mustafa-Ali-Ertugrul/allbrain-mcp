"""Unit tests for memory_domain_items pure functions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from allbrain.domains.memory.memory.memory_domain_items import (
    _collaboration_items,
    _file_modification_items,
    _goal_items,
    _governance_items,
    _organizational_items,
    _runtime_core_items,
    _session_items,
)
from allbrain.domains.memory.memory.semantic_memory import SemanticMemory
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


def make_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    id: str = "evt_1",
    project_id: int = 1,
    session_id: int = 1,
    agent_id: str | None = "codex",
    source: str = "test",
    file_path: str | None = None,
    task_hint: str | None = None,
    importance: int | None = 3,
    created_at: datetime | None = None,
) -> EventRead:
    return EventRead(
        id=id,
        project_id=project_id,
        session_id=session_id,
        agent_id=agent_id,
        type=event_type,
        source=source,
        file_path=file_path,
        payload=payload,
        task_hint=task_hint,
        importance=importance,
        created_at=created_at or datetime.now(UTC),
    )


def test_session_items() -> None:
    semantic = SemanticMemory()
    events = [
        make_event(
            EventType.SESSION_SUMMARY.value,
            {
                "session_id": "sess_100",
                "goals": ["Refactor auth", "Add tests"],
                "files": ["src/auth.py"],
                "tools": ["save_event", "list_events"],
                "errors": ["TimeoutError"],
                "status": "completed",
                "agent": "builder",
            },
            id="e_sess_1",
        ),
        make_event(
            EventType.SESSION_SUMMARY.value,
            {
                "status": "active",
            },
            id="e_sess_2",
            session_id=2,
            agent_id=None,
        ),
        make_event(EventType.TASK_CREATED.value, {}, id="e_other"),
    ]

    items = _session_items(events, semantic)

    assert len(items) == 2
    item1 = items[0]
    assert item1.id == "session:sess_100"
    assert "status=completed" in item1.content
    assert "agent=builder" in item1.content
    assert "errors=TimeoutError" in item1.content
    assert item1.importance_score == 0.8
    assert item1.tags["kind"] == "session"

    item2 = items[1]
    assert item2.id == "session:2"
    assert "errors=none" in item2.content
    assert item2.importance_score == 0.65


def test_goal_items() -> None:
    semantic = SemanticMemory()
    events = [
        make_event(
            EventType.GOAL_SET.value,
            {"goal": "Implement rate limiting", "status": "active"},
            id="e_goal_1",
            agent_id="planner",
        ),
        make_event(
            EventType.GOAL_SET.value,
            {"summary": "Secondary fallback goal"},
            id="e_goal_2",
            agent_id=None,
        ),
        make_event(
            EventType.GOAL_SET.value,
            {"goal": "Task scoped goal", "task_id": "task_123"},
            id="e_goal_skip",
        ),
        make_event(EventType.GOAL_SET.value, {}, id="e_goal_empty"),
    ]

    items = _goal_items(events, semantic)

    assert len(items) == 2
    assert items[0].id == "goal:e_goal_1"
    assert "Implement rate limiting" in items[0].content
    assert items[0].tags["kind"] == "goal"
    assert items[0].tags["status"] == "active"

    assert items[1].id == "goal:e_goal_2"
    assert "Secondary fallback goal" in items[1].content


def test_file_modification_items() -> None:
    semantic = SemanticMemory()
    events = [
        make_event(
            EventType.FILE_MODIFIED.value,
            {"change_kind": "edit", "confidence": "high"},
            id="e_file_1",
            file_path="src/main.py",
            agent_id="coder",
        ),
        make_event(
            EventType.FILE_MODIFIED.value,
            {"change_kind": "format", "confidence": "high"},
            id="e_file_2",
            file_path="src/main.py",
            agent_id="formatter",
        ),
        make_event(
            EventType.FILE_MODIFIED.value,
            {"change_kind": "create"},
            id="e_file_3",
            file_path="tests/test_main.py",
        ),
        make_event(EventType.FILE_MODIFIED.value, {}, id="e_file_nopath", file_path=None),
    ]

    items = _file_modification_items(events, semantic)

    assert len(items) == 2
    main_item = next(item for item in items if item.id == "file:src/main.py")
    assert "count=2" in main_item.content
    assert "changes=edit,format" in main_item.content
    assert main_item.tags["kind"] == "file_modification"
    assert len(main_item.source_event_ids) == 2


def test_collaboration_items() -> None:
    semantic = SemanticMemory()
    events = [
        make_event(
            EventType.TASK_ASSIGNED.value,
            {"collaboration_id": "collab_1", "objective": "Multi-agent review"},
            id="e_collab_1",
            agent_id="agent_a",
        ),
        make_event(
            EventType.COLLABORATION_COMPLETED.value,
            {"collaboration_id": "collab_1"},
            id="e_collab_2",
            agent_id="agent_b",
        ),
        make_event(
            EventType.COLLABORATION_FAILED.value,
            {"collaboration_id": "collab_2"},
            id="e_collab_3",
        ),
        make_event(
            EventType.TASK_ASSIGNED.value,
            {"collaboration_id": "collab_3"},
            id="e_collab_4",
        ),
    ]

    items = _collaboration_items(events, semantic)

    assert len(items) == 3
    collab1 = next(item for item in items if item.id == "collaboration:collab_1")
    assert "Multi-agent review" in collab1.content
    assert "status=success" in collab1.content
    assert collab1.importance_score == 0.8

    collab2 = next(item for item in items if item.id == "collaboration:collab_2")
    assert "status=failed" in collab2.content
    assert collab2.importance_score == 0.7

    collab3 = next(item for item in items if item.id == "collaboration:collab_3")
    assert "status=active" in collab3.content


def test_organizational_items() -> None:
    semantic = SemanticMemory()
    events = [
        make_event(
            EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value,
            {"pattern_id": "pat_1", "kind": "anti_pattern", "summary": "Circular dependency", "confidence": 0.85},
            id="e_org_1",
        ),
        make_event(
            EventType.RECOMMENDATION_GENERATED.value,
            {"recommendation_id": "rec_1", "kind": "architecture", "subject": "Split module", "confidence": 0.9},
            id="e_org_2",
        ),
    ]

    items = _organizational_items(events, semantic)

    assert len(items) == 2
    pat = next(item for item in items if item.id == "organizational_pattern:pat_1")
    assert "Circular dependency" in pat.content
    assert pat.importance_score == 0.85

    rec = next(item for item in items if item.id == "recommendation:rec_1")
    assert "Split module" in rec.content
    assert rec.importance_score == 0.9


def test_governance_items() -> None:
    semantic = SemanticMemory()
    events = [
        make_event(
            EventType.GOVERNANCE_DECISION_SYNTHESIZED.value,
            {
                "decision_id": "dec_1",
                "decision": "approve",
                "review_id": "rev_99",
                "alignment_score": 0.95,
                "trajectory_score": 0.88,
                "confidence": 0.85,
            },
            id="e_gov_1",
        ),
        make_event(
            EventType.GOVERNANCE_ALIGNMENT_EVALUATED.value,
            {
                "report_id": "rep_1",
                "review_id": "rev_99",
                "alignment_score": 0.8,
                "long_term_drift_score": 0.05,
                "safety_alignment_score": 0.9,
            },
            id="e_gov_2",
        ),
    ]

    items = _governance_items(events, semantic)

    assert len(items) == 2
    dec = next(item for item in items if item.id == "governance_decision:dec_1")
    assert "governance decision approve" in dec.content
    assert dec.tags["decision"] == "approve"

    rep = next(item for item in items if item.id == "alignment_report:rep_1")
    assert "alignment report score=0.8" in rep.content
    assert abs(rep.importance_score - 0.2) < 1e-5


def test_runtime_core_items() -> None:
    semantic = SemanticMemory()
    events = [
        make_event(
            EventType.FINAL_DECISION_RECORDED.value,
            {"run_id": "run_1", "action": "deploy", "reason": "Passed all gates", "confidence": 0.95},
            id="e_rt_1",
        ),
        make_event(
            EventType.RUNTIME_FEEDBACK_RECORDED.value,
            {"run_id": "run_1", "status": "ok", "execute_mode": "live"},
            id="e_rt_2",
        ),
        make_event(
            EventType.PREDICTION_ERROR_DETECTED.value,
            {"run_id": "run_1", "error_delta": 0.15},
            id="e_rt_3",
        ),
        make_event(
            EventType.FINAL_DECISION_RECORDED.value,
            {"action": "no_run_id"},
            id="e_rt_skip",
        ),
    ]

    items = _runtime_core_items(events, semantic)

    assert len(items) == 3
    dec = next(item for item in items if item.id == "runtime_final_decision:run_1")
    assert "action=deploy" in dec.content

    fb = next(item for item in items if item.id == "runtime_feedback:run_1")
    assert "status=ok" in fb.content

    err = next(item for item in items if item.id == "prediction_error:e_rt_3")
    assert "delta=0.15" in err.content
    assert err.importance_score == 0.9
