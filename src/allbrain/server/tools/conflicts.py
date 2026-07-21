"""Domain module: conflicts."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.domains.analysis.context.parallel_builder import ParallelContextBuilder
from allbrain.domains.collaboration.conflict.detector import ConflictDetector
from allbrain.domains.collaboration.conflict.resolver import ConflictResolver
from allbrain.models.schemas import (
    ConflictInput,
    ToolResult,
)
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
)
from allbrain.server.tools.decorators import handle_tool_errors

logger = logging.getLogger(__name__)


@handle_tool_errors
def detect_conflicts_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = ConflictInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
    conflicts = ConflictDetector().detect(events, threshold=data.threshold)
    audit_tool_call(
        context,
        tool_name="detect_conflicts",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data={"conflicts": conflicts, "count": len(conflicts)})


@handle_tool_errors
def resolve_conflicts_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = ConflictInput.model_validate(kwargs)
    bound_session_id = bind_session_id(context, None)
    events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
    conflicts = ConflictDetector().detect(events, threshold=data.threshold)
    agent_view = ParallelContextBuilder().build_agent_view(events)
    resolved = ConflictResolver().resolve(conflicts, events, agent_view)
    audit_tool_call(
        context,
        tool_name="resolve_conflicts",
        tool_args=data.model_dump(mode="json"),
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data={"resolved_conflicts": resolved, "count": len(resolved)})


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def detect_conflicts(limit: int = 5000, threshold: float = 0.7) -> dict[str, Any]:
        """Find contradictory semantic states between agents in the event log.

        Use this to detect when multiple agents have produced conflicting outputs
        or when the same task has been approached differently by different agents.
        This operates at the memory/state level, comparing agent outputs.

        Use `detect_contradictions` for logical/statement-level inconsistencies.

        Side effects: Read-only operation; scans events for semantic conflicts.

        Args:
            limit: Maximum number of events to scan (default 5000).
            threshold: Similarity threshold for conflict detection (default 0.7).
                Lower values are more sensitive; 0.7-0.9 is recommended.

        Returns:
            List of detected conflicts with conflicting event pairs, similarity scores,
            and suggested resolution strategies.
        """
        result = detect_conflicts_impl(context, limit=limit, threshold=threshold)
        return result.model_dump(mode="json")

    @mcp.tool
    def resolve_conflicts(limit: int = 5000, threshold: float = 0.7) -> dict[str, Any]:
        """Resolve detected conflicts automatically using conflict resolution algorithms.

        Use this after `detect_conflicts` to get resolved versions of conflicting states.
        The resolver uses heuristics like recency, agent reliability scores, and
        semantic similarity to produce a consolidated view.

        Side effects: Read-only operation; does not modify the event log.

        Args:
            limit: Maximum number of events to scan (default 5000).
            threshold: Similarity threshold for conflict detection (default 0.7).

        Returns:
            List of resolved conflicts with the chosen resolution, confidence score,
            and the resolved state for each conflict.
        """
        result = resolve_conflicts_impl(context, limit=limit, threshold=threshold)
        return result.model_dump(mode="json")
