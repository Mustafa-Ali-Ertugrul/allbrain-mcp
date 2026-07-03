"""Domain module: git."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.models.schemas import (
    GitContextInput,
    RecentChangesInput,
    ToolResult,
    UserInputError,
)
from allbrain.resume.gitbrain import GitBrain
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
)

logger = logging.getLogger(__name__)


def get_git_context_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = GitContextInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        git_context = GitBrain(project_path).build_git_context()
        audit_tool_call(
            context,
            tool_name="get_git_context",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=git_context)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_git_status_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = GitContextInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        git_status = GitBrain(project_path).get_status()
        audit_tool_call(
            context,
            tool_name="get_git_status",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=git_status)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_recent_changes_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = RecentChangesInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
        recent_changes = GitBrain(project_path).get_recent_changes(limit=data.limit)
        audit_tool_call(
            context,
            tool_name="get_recent_changes",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=recent_changes)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def get_git_context() -> dict[str, Any]:
        """Return current git branch, recent commits, and remote state.

        Safely inspects the project's git repo without modifying it. Returns
        empty values when the project is not a git repository.

        When to use: before any git-aware operation to understand the current
        branch, unpushed commits, and working tree state.
        """
        result = get_git_context_impl(context)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_git_status() -> dict[str, Any]:
        """Return git working tree status (modified, staged, untracked files).

        Safe in non-git repos — returns empty status without error.

        When to use: to check what files have changed, what is staged, or what
        untracked work exists before a commit or branch switch.
        """
        result = get_git_status_impl(context)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_recent_changes(limit: int = 10) -> dict[str, Any]:
        """Return the most recent git commits as a structured list.

        Each commit entry includes hash, author, date, and message. Safe in
        non-git repos — returns empty list.

        When to use: to review recent project history, understand what changed
        and by whom, or check if a particular change has been committed.
        """
        result = get_recent_changes_impl(context, limit=limit)
        return result.model_dump(mode="json")
