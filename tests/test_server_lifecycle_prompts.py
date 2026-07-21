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
    assert "No project found" in res1[0]["content"]

    res2 = registered_prompts["task_handoff"]("task_1", "agent_a")
    assert "no project found" in res2[0]["content"]

    res3 = registered_prompts["investigate_conflict"](99)
    assert "no project found" in res3[0]["content"]

    # 2. Project found branch
    project = MagicMock()
    project.id = 1
    ctx.repository.get_project_by_path.return_value = project
    ctx.repository.list_events.return_value = []

    with patch("allbrain.server.prompts.load_events_through_cursor", return_value=[]), \
         patch("allbrain.server.prompts.load_task_projection", return_value=({"tasks": {"t1": {"status": "open"}}}, {})):
        
        resume_res = registered_prompts["resume_project"]()
        assert len(resume_res) == 2
        assert "Context summary" in resume_res[0]["content"]

        handoff_res = registered_prompts["task_handoff"]("t1", "agent_a", reason="busy")
        assert "Handoff task t1" in handoff_res[0]["content"]


def test_conflict_summary_and_json_text():
    summary = _build_conflict_summary(1, "agent_x", [])
    assert "agent_x" in summary
    assert _json_text({"a": 1}) == '{"a": 1}'
