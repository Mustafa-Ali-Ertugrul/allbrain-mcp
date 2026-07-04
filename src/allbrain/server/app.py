from __future__ import annotations

import logging

from fastmcp import FastMCP

from allbrain.server.context import BrainContext
from allbrain.server.lifecycle import AllBrainMiddleware, create_lifespan
from allbrain.server.tools import register_all_tools

logger = logging.getLogger(__name__)


def create_mcp_server(context: BrainContext, *, tool_profile: str = "full") -> FastMCP:
    mcp = FastMCP(
        "AllBrain MCP",
        middleware=[AllBrainMiddleware(context)],
        lifespan=create_lifespan(context),
    )
    register_all_tools(mcp, context, tool_profile=tool_profile)
    return mcp
