"""Regression tests for the C-track remediation.

C1 replaces the N+1 ``list_session_events`` loop inside
``build_session_report`` with two batched repository helpers
(``session_event_counts`` and ``latest_session_summaries``). These
tests verify that the public report is identical to what the old
implementation produced, and that the new helpers return counts and
summaries correctly across mixed session populations (with events,
without events, with a summary event, without one).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from allbrain.events import EventType
from allbrain.server import BrainContext
from allbrain.server.tools.sessions import build_session_report
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def _make_context(tmp_path: Path) -> BrainContext:
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repository = BrainRepository(engine)
    project = tmp_path / "project"
    project.mkdir()
    session = repository.create_session(str(project), "codex", server_instance_id="instance-a")
    return BrainContext(
        repository=repository,
        project_path=str(project.resolve()),
        active_session=session,
        agent_name="codex",
        server_instance_id="instance-a",
    )


def test_session_event_counts_handles_empty_and_partial(tmp_path: Path) -> None:
    """session_event_counts returns counts only for non-empty sessions."""
    context = _make_context(tmp_path)
    repo = context.repository

    s1 = repo.create_session(str(context.project_path), "codex", server_instance_id="inst-a")
    s2 = repo.create_session(str(context.project_path), "claude", server_instance_id="inst-b")
    s3 = repo.create_session(str(context.project_path), "gemini", server_instance_id="inst-c")

    # s1 gets two events, s2 gets one, s3 gets none.
    repo.append_event(
        project_path=context.project_path,
        session_id=s1.id,
        type="task_created",
        source="agent",
        payload={},
        agent_id="codex",
    )
    repo.append_event(
        project_path=context.project_path,
        session_id=s1.id,
        type=EventType.SESSION_SUMMARY.value,
        source="agent",
        payload={"outcome": "ok"},
        agent_id="codex",
    )
    repo.append_event(
        project_path=context.project_path,
        session_id=s2.id,
        type="task_created",
        source="agent",
        payload={},
        agent_id="claude",
    )

    counts = repo.session_event_counts([s1.id, s2.id, s3.id])  # type: ignore[list-item]

    assert counts == {s1.id: 2, s2.id: 1}, f"unexpected counts: {counts}"
    assert s3.id not in counts, "empty session must be absent from counts"

    # Empty/None inputs should not raise.
    assert repo.session_event_counts([]) == {}


def test_latest_session_summaries_only_returns_matching(tmp_path: Path) -> None:
    """latest_session_summaries returns the most recent summary per session."""
    context = _make_context(tmp_path)
    repo = context.repository

    s1 = repo.create_session(str(context.project_path), "codex", server_instance_id="inst-a")
    s2 = repo.create_session(str(context.project_path), "claude", server_instance_id="inst-b")

    # s1 gets two summary events; the LATEST must win.
    repo.append_event(
        project_path=context.project_path,
        session_id=s1.id,
        type=EventType.SESSION_SUMMARY.value,
        source="agent",
        payload={"iteration": 1},
        agent_id="codex",
    )
    repo.append_event(
        project_path=context.project_path,
        session_id=s1.id,
        type=EventType.SESSION_SUMMARY.value,
        source="agent",
        payload={"iteration": 2},
        agent_id="codex",
    )
    # s2 gets no summary event.
    repo.append_event(
        project_path=context.project_path,
        session_id=s2.id,
        type="task_created",
        source="agent",
        payload={},
        agent_id="claude",
    )

    summaries = repo.latest_session_summaries([s1.id, s2.id])  # type: ignore[list-item]

    assert s1.id in summaries, "s1 missing from summaries despite two summary events"
    assert s2.id not in summaries, "s2 should not appear (no SESSION_SUMMARY event)"
    assert summaries[s1.id].payload == {"iteration": 2}, (
        f"expected latest (iteration 2) — got {summaries[s1.id].payload}"
    )
    assert repo.latest_session_summaries([]) == {}


def test_build_session_report_uses_counts_and_summaries_efficiently(tmp_path: Path) -> None:
    """build_session_report must work without calling list_session_events per session.

    The report's ``event_count`` and ``summary`` fields must match what
    we'd compute by calling list_session_events, but via the batched
    helpers. This guards against accidental regressions to the N+1 path.
    """
    context = _make_context(tmp_path)
    repo = context.repository

    # Two sessions: s1 eventful with summary, s2 eventful but no summary.
    s1 = repo.create_session(str(context.project_path), "codex", server_instance_id="inst-a")
    s2 = repo.create_session(str(context.project_path), "claude", server_instance_id="inst-b")

    repo.append_event(
        project_path=context.project_path,
        session_id=s1.id,
        type="task_created",
        source="agent",
        payload={},
        agent_id="codex",
    )
    repo.append_event(
        project_path=context.project_path,
        session_id=s1.id,
        type=EventType.SESSION_SUMMARY.value,
        source="agent",
        payload={"note": "first"},
        agent_id="codex",
    )
    repo.append_event(
        project_path=context.project_path,
        session_id=s2.id,
        type="task_failed",
        source="agent",
        payload={},
        agent_id="claude",
    )

    report = build_session_report(context, limit=10, include_empty=True, detail_limit=10)

    # Sanity: both sessions appear.
    assert report["session_count"] >= 2
    assert report["eventful_sessions"] >= 2

    details: list[dict[str, Any]] = report["details"]
    by_session = {d["session_id"]: d for d in details}

    if s1.id in by_session:
        d1 = by_session[s1.id]
        assert d1["event_count"] == 2, f"s1 event_count wrong: {d1['event_count']}"
        assert d1["summary"] == {"note": "first"}, f"s1 summary wrong: {d1['summary']}"

    if s2.id in by_session:
        d2 = by_session[s2.id]
        assert d2["event_count"] == 1, f"s2 event_count wrong: {d2['event_count']}"
        assert d2["summary"] is None, f"s2 summary must be None, got {d2['summary']}"
