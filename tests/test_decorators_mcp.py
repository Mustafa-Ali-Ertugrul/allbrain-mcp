"""Tests for handle_tool_errors_mcp (async-safe MCP envelope decorator).

These tests intentionally import the decorator module *inside* each test to
avoid cross-module stub contamination from test_decorators_exception_handling,
which monkey-patches sys.modules with fake schemas modules at import time.
"""

from __future__ import annotations

import asyncio
import sys

import pytest


def _load() -> tuple:
    """Import the real decorator module and its bound exception classes.

    Drops any stale ``allbrain.server.tools.decorators`` entry from
    sys.modules first, so the module re-binds to the genuine
    ``allbrain.models.schemas`` classes even if a prior test module stubbed
    them out in sys.modules.
    """
    sys.modules.pop("allbrain.server.tools.decorators", None)
    from allbrain.models.schemas import ToolResult, UserInputError
    from allbrain.server.tools.decorators import (
        handle_tool_errors,
        handle_tool_errors_mcp,
    )

    return ToolResult, UserInputError, handle_tool_errors, handle_tool_errors_mcp


def test_mcp_sync_validation_error_masked() -> None:
    ToolResult, _UI, _legacy, mcp = _load()

    @mcp
    def _tool() -> ToolResult:
        from pydantic import BaseModel

        class M(BaseModel):
            x: int

        M(x="not-an-int")  # raises ValidationError
        return ToolResult(ok=True)

    result = _tool()
    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert result.error_code == "validation_error"


def test_mcp_sync_user_input_error_masked() -> None:
    ToolResult, UserInputError, _legacy, mcp = _load()

    @mcp
    def _tool() -> ToolResult:
        raise UserInputError("naughty input with sk-ant-SECRETBYTE0123456789")

    result = _tool()
    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert result.error_code == "user_input_error"
    # secret pattern masked even in user input
    assert "sk-ant-" not in result.error


def test_mcp_sync_unexpected_exception_raises_tool_error() -> None:
    from fastmcp.exceptions import ToolError

    _ToolResult, _UI, _legacy, mcp = _load()

    @mcp
    def _tool() -> _ToolResult:
        raise RuntimeError("boom")

    with pytest.raises(ToolError):
        _tool()


def test_mcp_async_validation_error_masked() -> None:
    ToolResult, _UI, _legacy, mcp = _load()

    @mcp
    async def _tool() -> ToolResult:
        from pydantic import BaseModel

        class M(BaseModel):
            x: int

        M(x="bad")
        return ToolResult(ok=True)

    result = asyncio.run(_tool())
    assert result.ok is False
    assert result.error_code == "validation_error"


def test_mcp_async_unexpected_exception_raises_tool_error() -> None:
    from fastmcp.exceptions import ToolError

    _ToolResult, _UI, _legacy, mcp = _load()

    @mcp
    async def _tool() -> _ToolResult:
        raise RuntimeError("async boom")

    with pytest.raises(ToolError):
        asyncio.run(_tool())


def test_mcp_async_success_passthrough() -> None:
    ToolResult, _UI, _legacy, mcp = _load()

    @mcp
    async def _tool() -> ToolResult:
        return ToolResult(ok=True, data={"v": 1})

    result = asyncio.run(_tool())
    assert result.ok is True
    assert result.data == {"v": 1}


def test_legacy_sync_decorator_unchanged() -> None:
    """The original handle_tool_errors must keep returning ToolResult for
    unexpected exceptions (backward-compatible contract)."""
    ToolResult, _UI, legacy, _mcp = _load()

    @legacy
    def _tool() -> ToolResult:
        raise RuntimeError("legacy boom")

    result = _tool()
    # Legacy decorator still returns a ToolResult-shaped object (ok=False).
    assert getattr(result, "ok", None) is False
    assert result.error == "Internal server error"
    assert result.error_code == "internal_error"
