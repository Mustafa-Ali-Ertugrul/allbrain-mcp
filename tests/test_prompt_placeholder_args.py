"""Regression tests: prompts must tolerate MCP client placeholder arguments.

OpenCode prefetches prompts with literal template placeholders (e.g. ``"$1"``)
before real values exist. These previously crashed FastMCP with
``Could not convert argument`` (int params) and ``messages[0] must be Message
or str, got dict`` (dict messages). Both must now render cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from allbrain.server.app import create_mcp_server
from tests._helpers import make_context


@pytest.mark.asyncio
async def test_prompts_render_with_literal_placeholder_args(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    mcp = create_mcp_server(ctx, tool_profile="full")

    resume = await mcp.render_prompt("resume_project", {"limit": "$1"})
    assert resume.messages
    assert "Resume work on project" in resume.messages[0].content.text

    handoff = await mcp.render_prompt(
        "task_handoff",
        {"task_id": "$1", "from_agent": "$2"},
    )
    assert handoff.messages
    assert "Handoff task $1" in handoff.messages[0].content.text

    conflict = await mcp.render_prompt("investigate_conflict", {"session_id": "$1"})
    assert conflict.messages
    assert "Invalid session_id" in conflict.messages[0].content.text


@pytest.mark.asyncio
async def test_prompt_roles_and_conflict_content(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    mcp = create_mcp_server(ctx, tool_profile="full")

    resume = await mcp.render_prompt("resume_project", {"limit": "10"})
    assert [m.role for m in resume.messages] == ["user", "assistant"]

    sid = ctx.active_session.id
    conflict = await mcp.render_prompt("investigate_conflict", {"session_id": str(sid)})
    assert len(conflict.messages) == 2
    assert f"Investigate conflict in session {sid}" in conflict.messages[0].content.text
