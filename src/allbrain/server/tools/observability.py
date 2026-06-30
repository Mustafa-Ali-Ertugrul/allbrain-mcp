"""Domain module: observability."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.api.observability_api import ObservabilityAPI
from allbrain.models.schemas import (
    OrchestratorInput,
    ToolResult,
    UserInputError,
)
from allbrain.observability import ObservabilityBuilder
from allbrain.reliability.metrics import ReliabilityMetrics
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

logger = logging.getLogger(__name__)


def get_observability_dashboard_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = OrchestratorInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
        audit_tool_call(
            context,
            tool_name="get_observability_dashboard",
            tool_args={"limit": data.limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=ObservabilityBuilder().build(events))
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def replay_workflow_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=project_path, limit=limit)
        replay = ObservabilityAPI().replay(
            events,
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
            cursor=int(kwargs.get("cursor", 0) or 0),
            step_count=kwargs.get("step_count"),
            deterministic=bool(kwargs.get("deterministic", True)),
        )
        replay = replay | {
            "tasks": replay["visualization"]["tasks"],
            "task_count": replay["visualization"]["task_count"],
        }
        audit_tool_call(
            context,
            tool_name="replay_workflow",
            tool_args={
                "project_path": kwargs.get("project_path"),
                "workflow_id": kwargs.get("workflow_id"),
                "task_id": kwargs.get("task_id"),
                "cursor": kwargs.get("cursor", 0),
                "step_count": kwargs.get("step_count"),
                "deterministic": kwargs.get("deterministic", True),
                "limit": limit,
            },
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=replay)
    except (ValidationError, ValueError, TypeError) as exc:
        return ToolResult(ok=False, error=str(exc))


def get_workflow_trace_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        result = ObservabilityAPI().workflow_trace(
            events,
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        audit_tool_call(
            context,
            tool_name="get_workflow_trace",
            tool_args={
                "workflow_id": kwargs.get("workflow_id"),
                "task_id": kwargs.get("task_id"),
                "limit": limit,
            },
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_system_metrics_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        result = ObservabilityAPI().system_metrics(events)
        result["reliability"] = ReliabilityMetrics().build(events)
        audit_tool_call(
            context,
            tool_name="get_system_metrics",
            tool_args={"limit": limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_reliability_status_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        result = ReliabilityMetrics().build(events)
        audit_tool_call(
            context,
            tool_name="get_reliability_status",
            tool_args={"limit": limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def get_workflow_graph_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        result = ObservabilityAPI().graph(
            events,
            workflow_id=kwargs.get("workflow_id"),
            task_id=kwargs.get("task_id"),
        )
        audit_tool_call(
            context,
            tool_name="get_workflow_graph",
            tool_args={
                "workflow_id": kwargs.get("workflow_id"),
                "task_id": kwargs.get("task_id"),
                "limit": limit,
            },
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=result)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def compare_agents_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = OrchestratorInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
        comparison = ObservabilityBuilder().agent_comparison(events)
        audit_tool_call(
            context,
            tool_name="compare_agents",
            tool_args={"limit": data.limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=comparison)
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def get_observability_dashboard(limit: int = 5000) -> dict[str, Any]:
        result = get_observability_dashboard_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_workflow_trace(
        workflow_id: str | None = None,
        task_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_workflow_trace_impl(
            context,
            workflow_id=workflow_id,
            task_id=task_id,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_system_metrics(limit: int = 5000) -> dict[str, Any]:
        result = get_system_metrics_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_reliability_status(limit: int = 5000) -> dict[str, Any]:
        result = get_reliability_status_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def replay_workflow(
        workflow_id: str | None = None,
        task_id: str | None = None,
        cursor: int = 0,
        step_count: int | None = None,
        deterministic: bool = True,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = replay_workflow_impl(
            context,
            workflow_id=workflow_id,
            task_id=task_id,
            cursor=cursor,
            step_count=step_count,
            deterministic=deterministic,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def get_workflow_graph(
        workflow_id: str | None = None,
        task_id: str | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        result = get_workflow_graph_impl(
            context,
            workflow_id=workflow_id,
            task_id=task_id,
            limit=limit,
        )
        return result.model_dump(mode="json")

    @mcp.tool
    def compare_agents(limit: int = 5000) -> dict[str, Any]:
        result = compare_agents_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")
