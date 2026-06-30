"""Domain module: ui."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.models.schemas import (
    ToolResult,
    UserInputError,
)
from allbrain.security.rate_limit import check_tool_rate
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    datetime_now_iso,
    filter_observability_events,
    maybe_auto_snapshot,
    observability_project_and_limit,
)
from allbrain.ui import GraphExplorer, MetricsDashboard, ReplayViewer, TraceViewer

logger = logging.getLogger(__name__)


def get_ui_trace_view_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = filter_observability_events(
            context.repository.list_events(project_path=context.project_path, limit=limit),
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        view = TraceViewer().build(events)
        audit_tool_call(
            context,
            tool_name="get_ui_trace_view",
            tool_args={"workflow_id": kwargs.get("workflow_id"), "task_id": kwargs.get("task_id"), "limit": limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=view)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_ui_replay_view_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = filter_observability_events(
            context.repository.list_events(project_path=context.project_path, limit=limit),
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        view = ReplayViewer().build(
            events,
            cursor=int(kwargs.get("cursor", 0) or 0),
            step_count=kwargs.get("step_count"),
        )
        audit_tool_call(
            context,
            tool_name="get_ui_replay_view",
            tool_args={
                "workflow_id": kwargs.get("workflow_id"),
                "task_id": kwargs.get("task_id"),
                "cursor": kwargs.get("cursor", 0),
                "step_count": kwargs.get("step_count"),
                "limit": limit,
            },
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=view)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_ui_graph_view_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = filter_observability_events(
            context.repository.list_events(project_path=context.project_path, limit=limit),
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        view = GraphExplorer().build(events)
        audit_tool_call(
            context,
            tool_name="get_ui_graph_view",
            tool_args={"workflow_id": kwargs.get("workflow_id"), "task_id": kwargs.get("task_id"), "limit": limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=view)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_ui_metrics_view_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        view = MetricsDashboard().build(events)
        audit_tool_call(
            context,
            tool_name="get_ui_metrics_view",
            tool_args={"limit": limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=view)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def get_ui_trace_view(
        workflow_id: str | None = None,
        task_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_ui_trace_view_impl(
            context, project_path=context.project_path, workflow_id=workflow_id, task_id=task_id, limit=limit
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_ui_replay_view(
        workflow_id: str | None = None,
        task_id: str | None = None,
        cursor: int = 0,
        step_count: int | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_ui_replay_view_impl(
            context,
            workflow_id=workflow_id,
            task_id=task_id,
            cursor=cursor,
            step_count=step_count,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_ui_graph_view(
        workflow_id: str | None = None,
        task_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_ui_graph_view_impl(
            context, project_path=context.project_path, workflow_id=workflow_id, task_id=task_id, limit=limit
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_ui_metrics_view(limit: int = 5000) -> dict[str, Any]:
        result = get_ui_metrics_view_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")
