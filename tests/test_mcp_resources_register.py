"""Wiring tests: verify resources and prompts register on FastMCP."""

from __future__ import annotations

from pathlib import Path

import pytest

from allbrain.server.app import create_mcp_server
from allbrain.server.prompts import register_prompts
from allbrain.server.resources import register_resources
from tests._helpers import make_context


@pytest.mark.asyncio
async def test_register_resources_adds_five_resources(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    mcp = create_mcp_server(ctx, tool_profile="full")
    resources = await mcp.list_resources()
    templates = await mcp.list_resource_templates()
    resource_uris = {str(r.uri) for r in resources}
    template_uris = {str(t.uri_template) for t in templates}
    all_uris = resource_uris | template_uris
    assert "project://resume" in all_uris
    assert "tasks://graph" in all_uris
    assert "git://fingerprint" in all_uris
    assert "session://{session_id}/summary" in all_uris
    assert "event://{event_id}" in all_uris


@pytest.mark.asyncio
async def test_register_prompts_adds_three_prompts(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    mcp = create_mcp_server(ctx, tool_profile="full")
    prompts = await mcp.list_prompts()
    names = {p.name for p in prompts}
    assert "resume_project" in names
    assert "task_handoff" in names
    assert "investigate_conflict" in names


@pytest.mark.asyncio
async def test_create_mcp_server_has_resources_and_prompts(tmp_path: Path) -> None:
    ctx = make_context(tmp_path)
    mcp = create_mcp_server(ctx, tool_profile="full")
    resources = await mcp.list_resources()
    templates = await mcp.list_resource_templates()
    prompts = await mcp.list_prompts()
    resource_count = len(resources) + len(templates)
    assert resource_count == 5
    assert len(prompts) == 3
