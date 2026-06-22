from __future__ import annotations

from datetime import datetime
from pathlib import Path

from allbrain.events.schemas import EventType
from allbrain.replay import EventReplayEngine
from allbrain.revision import (
    RevisionManager,
    RevisionReducer,
    make_payload,
)


def _make_event(event_id: str, event_type: str, payload: dict | None = None, created_at: datetime | None = None):
    class _E:
        pass
    e = _E()
    e.id = event_id
    e.type = event_type
    e.payload = payload or {}
    e.created_at = created_at or datetime(2020, 1, 1)
    return e


def test_manager_equals_reducer_no_checkpoint():
    """When no BELIEF_REVISED event is in the log, both views return empty
    RevisionState (no recompute from intent events)."""
    events = [
        _make_event("1", EventType.TASK_COMPLETED.value, {"task_hint": "x"}),
        _make_event("2", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []}),
    ]
    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.confidence == 0.0
    assert r_state.confidence == 0.0
    assert m_state.revision_count == 0
    assert r_state.revision_count == 0
    assert m_state.contradiction_count == 0
    assert r_state.contradiction_count == 0
    assert m_state.old_confidence is None
    assert r_state.old_confidence is None


def test_manager_equals_reducer_with_checkpoint():
    """Both views return the same snapshot when BELIEF_REVISED is present."""
    payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.40,
        reason="contradiction",
        evidence_count=2,
    )
    e1 = _make_event("1", EventType.TASK_COMPLETED.value)
    e2 = _make_event("2", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []})
    e_revised = _make_event("3", EventType.BELIEF_REVISED.value, payload)

    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in [e1, e2, e_revised]:
        reducer.apply(e)

    m_state = manager.query([e1, e2, e_revised])
    r_state = reducer.snapshot()

    assert m_state.confidence == r_state.confidence
    assert m_state.old_confidence == r_state.old_confidence
    assert m_state.analysis_id == r_state.analysis_id


def test_convergence_with_mixed_log_and_trailing_contradictions():
    """Mixed log: task, contradiction, BELIEF_REVISED, more contradictions.

    The reducer's last bucket = last BELIEF_REVISED payload (authoritative).
    The manager finds that checkpoint, then counts CONTRADICTION_DETECTED
    events in the trailing slice and re-applies revise().

    Both must agree on:
      - confidence (revised from baseline + trailing penalties)
      - contradiction_count (trailing count)
      - analysis_id (sha256 of sorted seen_ids)
    """
    revised_payload = make_payload(
        context_key="default",
        old_confidence=0.90,
        new_confidence=0.40,
        reason="contradiction",
        evidence_count=2,
    )
    events = [
        _make_event("1", EventType.TASK_COMPLETED.value),
        _make_event("2", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []}),
        _make_event("3", EventType.BELIEF_REVISED.value, revised_payload),
        _make_event("4", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []}),
        _make_event("5", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []}),
    ]

    manager = RevisionManager()
    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    m_state = manager.query(events)
    r_state = reducer.snapshot()

    assert m_state.confidence == r_state.confidence
    assert m_state.contradiction_count == r_state.contradiction_count == 2
    assert m_state.analysis_id == r_state.analysis_id
    assert m_state.old_confidence == r_state.old_confidence == 0.40  # baseline = payload's new_confidence
    assert m_state.revision_count == r_state.revision_count == 1


def test_manager_equals_reducer_after_replay_round_trip():
    """Netleştirme 2 (mirrors contradiction): exact dict equality.

    final_state["revision"]["default"] == manager.query(events, "default").state-dict
    """
    revised_payload = make_payload(
        context_key="default",
        old_confidence=0.84,
        new_confidence=0.52,
        reason="contradiction",
        evidence_count=6,
    )
    events = [
        _make_event("1", EventType.TASK_COMPLETED.value),
        _make_event("2", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []}),
        _make_event("3", EventType.BELIEF_REVISED.value, revised_payload),
        _make_event("4", EventType.CONTRADICTION_DETECTED.value, {"context_key": "default", "contradictions": []}),
    ]

    engine = EventReplayEngine()
    final_state = engine.replay(events)["final_state"]

    reducer = RevisionReducer()
    for e in events:
        reducer.apply(e)

    expected = reducer.all_snapshots()["default"]

    assert final_state["revision"]["default"] == expected


def test_revision_quality_gate_no_uuid7_or_now_or_random_in_determinism_path():
    """Quality gate: estimator.py, reducer.py, manager.py must not use
    uuid7(), datetime.now(), random.*, or time.time() — deterministic
    hash only. Sprint 45 also covers the uncertainty module's estimator
    (composite_uncertainty is the new write-path's uncertainty source).

    The pipeline write-path (pipeline.py _revision_step /
    _uncertainty_computed_step) is exempt because it runs at runtime,
    not replay.
    """
    determinism_critical = ["estimator.py", "reducer.py", "manager.py"]
    base = Path("src/allbrain/revision")
    for filename in determinism_critical:
        content = (base / filename).read_text(encoding="utf-8")
        assert "uuid7" not in content, f"{filename} uses uuid7 — must be deterministic hash"
        assert "datetime.now" not in content, f"{filename} uses datetime.now — must be deterministic"
        assert "random." not in content, f"{filename} uses random — must be deterministic"
        assert "time.time" not in content, f"{filename} uses time.time — must be deterministic"

    uncertainty_critical = ["estimator.py"]
    base_u = Path("src/allbrain/uncertainty")
    for filename in uncertainty_critical:
        content = (base_u / filename).read_text(encoding="utf-8")
        assert "uuid7" not in content, f"uncertainty/{filename} uses uuid7 — must be deterministic hash"
        assert "datetime.now" not in content, f"uncertainty/{filename} uses datetime.now — must be deterministic"
        assert "random." not in content, f"uncertainty/{filename} uses random — must be deterministic"
        assert "time.time" not in content, f"uncertainty/{filename} uses time.time — must be deterministic"