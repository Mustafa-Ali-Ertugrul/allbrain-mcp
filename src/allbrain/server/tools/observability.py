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
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
    observability_project_and_limit,
)
from allbrain.snapshot.constants import NON_SEMANTIC_EVENT_TYPES

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
        viz = replay.get("visualization", {})
        replay = replay | {
            "tasks": viz.get("workflow_replay", {}).get("tasks", {}),
            "task_count": viz.get("workflow_replay", {}).get("task_count", 0),
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
        return ToolResult(ok=True, data={"replay": replay})
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
        from allbrain.server.tools.sessions import build_session_report

        result["sessions"] = build_session_report(
            context,
            limit=min(limit, 5000),
            include_empty=True,
            detail_limit=0,
        )

        semantic_events = [e for e in events if e.type not in NON_SEMANTIC_EVENT_TYPES]
        memory_event_count = len(semantic_events)
        memory_items = 0
        memory_categories: dict[str, int] = {}
        if memory_event_count > 0:
            try:
                from allbrain.memory import MemoryBuilder

                items = MemoryBuilder().build(events)
                memory_items = len(items)
                from collections import Counter

                memory_categories = dict(sorted(Counter(item.tags.get("kind", "other") for item in items).items()))
            except Exception:
                memory_items = 0
        result["memory_coverage"] = {
            "total_events": len(events),
            "semantic_event_count": memory_event_count,
            "memory_item_count": memory_items,
            "coverage_rate": round(memory_items / memory_event_count, 6) if memory_event_count else 0.0,
            "categories": memory_categories,
        }

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
        """Return an observability summary dashboard for the project.

        Aggregates agent selection decisions, workflow replay metrics, and agent
        comparison data into a single overview. Shows recent execution patterns,
        agent performance balance, and workflow activity at a glance.

        Use this as a starting point for understanding project health. For deeper
        analysis, use individual tools: `compare_agents`, `get_system_metrics`,
        `get_reliability_status`.

        Side effects: Read-only operation; builds view from event log.

        Args:
            limit: Maximum number of events to process (default 5000).

        Returns:
            Dashboard with agent performance summary, recent workflow metrics,
            and high-level system state.
        """
        result = get_observability_dashboard_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def workflow_info(
        view: str = "trace",
        workflow_id: str | None = None,
        task_id: str | None = None,
        cursor: int = 0,
        step_count: int | None = None,
        deterministic: bool = True,
        limit: int = 5000,
    ) -> dict[str, Any]:
        """Retrieve workflow execution data: trace, graph, or replay.

        Consolidated tool replacing `get_workflow_trace`, `get_workflow_graph`, and
        `replay_workflow`. Use the `view` parameter to select the representation.

        Side effects: Read-only operation. Does not modify event state.

        Args:
            view: Type of workflow data to return:
                - "trace": chronological execution trace with timestamps, agent
                  assignments, decisions, and state transitions (default)
                - "graph": structural DAG showing task dependencies and relationships
                - "replay": deterministic step-by-step replay from stored events
            workflow_id: Optional workflow ID to filter by.
            task_id: Optional task ID to filter by.
            cursor: Starting cursor position for replay (default 0). Only used when
                view is "replay".
            step_count: Number of steps to replay (None = all). Only used when view
                is "replay".
            deterministic: Whether to enforce seeded deterministic replay (default
                True). Only used when view is "replay".
            limit: Max events to process (default 5000).

        Returns:
            Workflow data in the requested view format: execution trace steps,
            graph nodes/edges, or replayed state transitions.
        """
        view_lower = view.lower()
        if view_lower == "graph":
            result = get_workflow_graph_impl(context, workflow_id=workflow_id, task_id=task_id, limit=limit)
        elif view_lower == "replay":
            result = replay_workflow_impl(
                context,
                workflow_id=workflow_id,
                task_id=task_id,
                cursor=cursor,
                step_count=step_count,
                deterministic=deterministic,
                limit=limit,
            )
        else:
            result = get_workflow_trace_impl(context, workflow_id=workflow_id, task_id=task_id, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_system_metrics(limit: int = 5000) -> dict[str, Any]:
        """Return system-level performance metrics (CPU, memory, event rates).

        Collects resource usage statistics, event throughput rates, and tool call
        frequency data. Includes reliability metrics like lease recovery rates and
        duplicate detection counts.

        Use this for monitoring server health, detecting resource bottlenecks, or
        performance tuning. `get_reliability_status` provides deeper durability and
        consistency indicators.

        Side effects: Read-only operation. Aggregates psutil-based resource usage
        and event processing rates.

        Args:
            limit: Maximum number of events to analyze (default 5000).

        Returns:
            System metrics with CPU, memory, event throughput, tool call frequency,
            and reliability indicators.
        """
        result = get_system_metrics_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def get_reliability_status(limit: int = 5000) -> dict[str, Any]:
        """Return reliability and durability metrics for the system.

        Aggregates lease recovery rates, duplicate detection counts, failure tallies,
        and session health data. Also computes memory coverage rates from semantic
        events versus total events.

        Use this to assess system health, investigate whether any events or leases
        have been lost or duplicated, and verify persistent storage consistency.

        Side effects: Read-only operation. Builds reliability report from event log.

        Args:
            limit: Maximum number of events to analyze (default 5000).

        Returns:
            Reliability report with lease statistics, failure counts, session
            summaries, memory coverage rates, and category breakdowns.
        """
        result = get_reliability_status_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def compare_agents(limit: int = 5000) -> dict[str, Any]:
        """Compare agent performance metrics side-by-side.

        Returns success rates, failure counts, blocked counts, assigned tasks,
        and confidence scores for each agent in the project. Builds an agent
        comparison matrix from event history.

        Use this to evaluate which agents are performing well, detect underperforming
        agents, or balance workload distribution across multi-agent systems.

        Side effects: Read-only operation. Aggregates from event log.

        Args:
            limit: Maximum number of events to process (default 5000).

        Returns:
            Agent comparison data with per-agent success rates, failure counts,
            task assignments, confidence scores, and performance rankings.
        """
        result = compare_agents_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")
