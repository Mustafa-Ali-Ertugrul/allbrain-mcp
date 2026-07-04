"""Domain module: git."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from allbrain.gitbrain.parser import GitBrain
from allbrain.models.schemas import (
    GitContextInput,
    RecentChangesInput,
    ToolResult,
    UserInputError,
    WorkSummaryInput,
)
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


def get_work_summary_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = WorkSummaryInput.model_validate(kwargs)
        bound_session_id = bind_session_id(context, None)
        summary = GitBrain(context.project_path).get_work_summary(
            since=data.since,
            until=data.until,
            limit=data.limit,
        )
        audit_tool_call(
            context,
            tool_name="get_work_summary",
            tool_args=data.model_dump(mode="json"),
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=summary)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def git_info(
        info_type: str = "all",
        limit: int = 100,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        """Retrieve git repository context, working tree status, or recent changes.

        Consolidated tool replacing the previous `get_git_context`, `get_git_status`,
        and `get_recent_changes` tools. Use `info_type` to select what subset to return.

        "all" returns branch, remote, recent commits, working tree status, and staged/
        modified/untracked file lists in a single response. Use this when you need the
        full picture before making changes.

        Side effects: Read-only operation; queries git repository.

        Args:
            info_type: What git information to return:
                - "all": branch, remote, commits, and working tree status (default)
                - "context": branch name, remote URL, list of recent commits
                - "status": working tree status with staged/modified/untracked files
                - "changes": recent commits from the current branch
                - "work_summary": date-filtered commit/file/line summary across all branches
            limit: Max commits to return (default 100). Work summaries report
                ``truncated=true`` when more commits exist in the time window.
            since: Optional inclusive ISO timestamp for "work_summary".
            until: Optional exclusive ISO timestamp for "work_summary".

        Returns:
            Git information dict with keys depending on info_type. "all" returns
            branch, remote, commits, status, and changes data.
        """
        info_type_lower = info_type.lower()
        result: dict[str, Any] = {}
        if info_type_lower in ("all", "context"):
            result["context"] = get_git_context_impl(context).data
        if info_type_lower in ("all", "status"):
            result["status"] = get_git_status_impl(context).data
        if info_type_lower in ("all", "changes"):
            result["changes"] = get_recent_changes_impl(context, limit=limit).data
        if info_type_lower == "work_summary":
            work_result = get_work_summary_impl(
                context,
                limit=limit,
                since=since,
                until=until,
            )
            if not work_result.ok:
                return work_result.model_dump(mode="json")
            result["work_summary"] = work_result.data
        return ToolResult(ok=True, data=result).model_dump(mode="json")
