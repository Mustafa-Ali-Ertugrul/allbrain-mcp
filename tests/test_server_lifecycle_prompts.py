from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from allbrain.server.context import BrainContext
from allbrain.server.lifecycle import _cleanup_loop, _heartbeat_loop, create_lifespan
from allbrain.server.prompts import _build_conflict_summary, _json_text, register_prompts


@pytest.mark.asyncio
async def test_lifecycle_heartbeat_and_cleanup_loops():
    ctx = MagicMock(spec=BrainContext)
    ctx._session_lock = MagicMock()
    ctx._session_lock.__enter__.return_value = None
    ctx._session_lock.__exit__.return_value = None

    active_session = MagicMock()
    active_session.id = 123
    ctx._active_session = active_session
    ctx.project_path = "/test/project"
    ctx.repository = MagicMock()

    # Run heartbeat loop for a short moment then cancel
    t1 = asyncio.create_task(_heartbeat_loop(ctx))
    await asyncio.sleep(0.01)
    t1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t1

    # Run cleanup loop for a short moment then cancel
    t2 = asyncio.create_task(_cleanup_loop(ctx))
    await asyncio.sleep(0.01)
    t2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t2


@pytest.mark.asyncio
async def test_heartbeat_loop_detaches_terminal_session(tmp_path):
    """A session closed by another process must be detached by the next beat.

    The zombie process must stop heartbeating a terminal row (heartbeat can
    never drift past ended_at) and drop it so the next tool call creates a
    fresh session instead of writing into a dead one.
    """
    from allbrain.models.entities import Session
    from allbrain.server.lifecycle_session import ensure_session_started
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db, open_session

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repository = BrainRepository(engine)
    project = tmp_path / "project"
    project.mkdir()
    ctx = BrainContext(
        repository=repository,
        project_path=str(project.resolve()),
        agent_name="codex",
        central_audit_enabled=True,
    )
    session = ensure_session_started(ctx)
    assert ctx.active_session is not None
    # Another process closes the session behind this process's back.
    closed = repository.close_session(session.id or 0, status="closed", reason="external")
    assert closed is not None
    assert closed.ended_at is not None
    ended = closed.ended_at

    with patch("allbrain.server.lifecycle.HEARTBEAT_INTERVAL_SECONDS", 0.01):
        task = asyncio.create_task(_heartbeat_loop(ctx))
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert ctx.active_session is None
    with open_session(engine) as db:
        stored = db.get(Session, session.id)
    assert stored is not None
    assert stored.status == "closed"
    assert stored.last_heartbeat_at == ended


@pytest.mark.asyncio
@pytest.mark.parametrize(("wall_elapsed", "expect_reconcile"), [(0.01, True), (10_000.0, False)])
async def test_cleanup_loop_skips_reconcile_after_host_suspend(wall_elapsed, expect_reconcile):
    """After laptop sleep every live heartbeat is old; reconciling then marks live sessions stale.

    The loop must detect it woke far later than scheduled and skip that round.
    """
    ctx = MagicMock(spec=BrainContext)
    ctx.project_path = "/test/project"
    ctx.repository = MagicMock()
    ctx.repository.cleanup_empty_sessions.return_value = 0
    reconcile = MagicMock(return_value=[])
    clock = iter([0.0] + [wall_elapsed * n for n in range(1, 100)])

    with (
        patch("allbrain.server.lifecycle.SESSION_CLEANUP_INTERVAL_SECONDS", 0.01),
        patch("allbrain.server.lifecycle.HEARTBEAT_INTERVAL_SECONDS", 0.01),
        patch("allbrain.server.lifecycle.reconcile_stale_sessions", reconcile),
        patch("allbrain.server.lifecycle.time.time", side_effect=lambda: next(clock)),
    ):
        task = asyncio.create_task(_cleanup_loop(ctx))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert reconcile.called is expect_reconcile
    assert ctx.record_cleanup_run.called


@pytest.mark.asyncio
async def test_create_lifespan_success_and_failure():
    ctx = MagicMock(spec=BrainContext)
    ctx._session_lock = MagicMock()
    ctx._active_session = None

    lifespan_fn = create_lifespan(ctx)

    # Success branch
    async with lifespan_fn(MagicMock()) as state:
        assert state["brain_context"] == ctx

    # Error branch
    with pytest.raises(RuntimeError):
        async with lifespan_fn(MagicMock()):
            raise RuntimeError("Boom")


def test_prompts_registration_and_execution():
    mcp = MagicMock()
    registered_prompts = {}

    def prompt_decorator(fn):
        registered_prompts[fn.__name__] = fn
        return fn

    mcp.prompt = prompt_decorator

    ctx = MagicMock(spec=BrainContext)
    ctx.project_path = "/test/project"

    # 1. No project branch
    ctx.repository.get_project_by_path.return_value = None
    register_prompts(mcp, ctx)

    res1 = registered_prompts["resume_project"]()
    assert "No project found" in res1.messages[0].content.text

    res2 = registered_prompts["task_handoff"]("task_1", "agent_a")
    assert "no project found" in res2.messages[0].content.text

    res3 = registered_prompts["investigate_conflict"]("99")
    assert "no project found" in res3.messages[0].content.text

    # 2. Project found branch
    project = MagicMock()
    project.id = 1
    ctx.repository.get_project_by_path.return_value = project
    ctx.repository.list_events.return_value = []

    with (
        patch("allbrain.server.prompts.load_events_through_cursor", return_value=[]),
        patch("allbrain.server.prompts.load_task_projection", return_value=({"tasks": {"t1": {"status": "open"}}}, {})),
    ):
        resume_res = registered_prompts["resume_project"]()
        assert len(resume_res.messages) == 2
        assert "Context summary" in resume_res.messages[0].content.text

        handoff_res = registered_prompts["task_handoff"]("t1", "agent_a", reason="busy")
        assert "Handoff task t1" in handoff_res.messages[0].content.text


def test_conflict_summary_and_json_text():
    summary = _build_conflict_summary(1, "agent_x", [])
    assert "agent_x" in summary
    assert _json_text({"a": 1}) == '{"a": 1}'
