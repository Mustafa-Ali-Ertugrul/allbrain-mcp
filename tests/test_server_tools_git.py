"""Tests for allbrain.server.tools.git — error branches + register_tools."""

from unittest.mock import MagicMock, patch
from pydantic import BaseModel, ValidationError

import pytest

from allbrain.models.schemas import ToolResult, UserInputError
from allbrain.server.context import BrainContext
from allbrain.server.tools.git import (
    get_git_context_impl,
    get_git_status_impl,
    get_recent_changes_impl,
    register_tools,
)


def _validation_error():
    """Build a real ValidationError instance for testing."""
    class _Dummy(BaseModel):
        x: int

    try:
        _Dummy(x="not_an_int")
    except ValidationError as exc:
        return exc


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=BrainContext)
    ctx.project_path = "/tmp/test-repo"
    ctx.agent_name = "test-agent"
    return ctx


class TestGetGitContextImpl:
    def test_validation_error(self, mock_context):
        with patch(
            "allbrain.server.tools.git.GitContextInput.model_validate",
            side_effect=_validation_error(),
        ):
            result = get_git_context_impl(mock_context)
        assert result.ok is False
        assert result.error is not None

    def test_user_input_error(self, mock_context):
        with patch(
            "allbrain.server.tools.git.GitContextInput.model_validate",
            side_effect=UserInputError("bad input"),
        ):
            result = get_git_context_impl(mock_context)
        assert result.ok is False
        assert result.error == "bad input"

    def test_unexpected_error(self, mock_context):
        with patch(
            "allbrain.server.tools.git.GitBrain",
            side_effect=Exception("boom"),
        ):
            result = get_git_context_impl(mock_context)
        assert result.ok is False
        assert result.error == "Internal server error"


class TestGetGitStatusImpl:
    def test_validation_error(self, mock_context):
        with patch(
            "allbrain.server.tools.git.GitContextInput.model_validate",
            side_effect=_validation_error(),
        ):
            result = get_git_status_impl(mock_context)
        assert result.ok is False
        assert result.error is not None


class TestGetRecentChangesImpl:
    def test_validation_error(self, mock_context):
        with patch(
            "allbrain.server.tools.git.RecentChangesInput.model_validate",
            side_effect=_validation_error(),
        ):
            result = get_recent_changes_impl(mock_context)
        assert result.ok is False
        assert result.error is not None


class TestRegisterTools:
    def test_git_info_returns_context(self, mock_context):
        with patch("allbrain.server.tools.git.get_git_context_impl") as mock_fn:
            mock_fn.return_value = ToolResult(ok=True, data={"branch": "main"})
            mcp = MagicMock()
            register_tools(mcp, mock_context)
            registered_fn = mcp.tool.call_args[0][0]
            result = registered_fn(info_type="context")
        assert result["ok"] is True
        assert result["data"]["context"] == {"branch": "main"}
        mock_fn.assert_called_once_with(mock_context)

    def test_git_info_returns_status(self, mock_context):
        with patch("allbrain.server.tools.git.get_git_status_impl") as mock_fn:
            mock_fn.return_value = ToolResult(ok=True, data={"staged": [], "modified": []})
            mcp = MagicMock()
            register_tools(mcp, mock_context)
            registered_fn = mcp.tool.call_args[0][0]
            result = registered_fn(info_type="status")
        assert result["ok"] is True
        assert result["data"]["status"] == {"staged": [], "modified": []}
        mock_fn.assert_called_once_with(mock_context)

    def test_git_info_returns_changes(self, mock_context):
        with patch("allbrain.server.tools.git.get_recent_changes_impl") as mock_fn:
            mock_fn.return_value = ToolResult(ok=True, data=[{"hash": "abc123", "message": "fix"}])
            mcp = MagicMock()
            register_tools(mcp, mock_context)
            registered_fn = mcp.tool.call_args[0][0]
            result = registered_fn(info_type="changes", limit=5)
        assert result["ok"] is True
        assert result["data"]["changes"] == [{"hash": "abc123", "message": "fix"}]
        mock_fn.assert_called_once_with(mock_context, limit=5)

    def test_git_info_all(self, mock_context):
        with (
            patch("allbrain.server.tools.git.get_git_context_impl") as mock_ctx,
            patch("allbrain.server.tools.git.get_git_status_impl") as mock_st,
            patch("allbrain.server.tools.git.get_recent_changes_impl") as mock_ch,
        ):
            mock_ctx.return_value = ToolResult(ok=True, data={"branch": "main"})
            mock_st.return_value = ToolResult(ok=True, data={"staged": []})
            mock_ch.return_value = ToolResult(ok=True, data=[{"hash": "abc"}])
            mcp = MagicMock()
            register_tools(mcp, mock_context)
            registered_fn = mcp.tool.call_args[0][0]
            result = registered_fn(info_type="all", limit=5)
        assert result["ok"] is True
        assert result["data"]["context"] == {"branch": "main"}
        assert result["data"]["status"] == {"staged": []}
        assert result["data"]["changes"] == [{"hash": "abc"}]
        mock_ctx.assert_called_once_with(mock_context)
        mock_st.assert_called_once_with(mock_context)
        mock_ch.assert_called_once_with(mock_context, limit=5)
