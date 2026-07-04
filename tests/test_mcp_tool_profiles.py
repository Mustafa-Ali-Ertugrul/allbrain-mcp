from __future__ import annotations

import pytest

from allbrain.server import create_mcp_server
from allbrain.server.tools import CORE_TOOL_NAMES
from tests._helpers import make_context


@pytest.mark.anyio
async def test_core_tool_profile_is_exact_and_unique(tmp_path) -> None:
    context = make_context(tmp_path)
    try:
        server = create_mcp_server(context, tool_profile="core")
        tools = await server.list_tools()
        names = [tool.name for tool in tools]
        assert set(names) == CORE_TOOL_NAMES
        assert len(names) == len(CORE_TOOL_NAMES) == 10
    finally:
        context.repository.close()


@pytest.mark.anyio
async def test_full_tool_profile_has_no_duplicate_pipeline_tool(tmp_path) -> None:
    context = make_context(tmp_path)
    try:
        server = create_mcp_server(context, tool_profile="full")
        names = [tool.name for tool in await server.list_tools()]
        assert len(names) == len(set(names))
        assert names.count("run_decision_pipeline") == 1
        assert CORE_TOOL_NAMES.issubset(names)
    finally:
        context.repository.close()
