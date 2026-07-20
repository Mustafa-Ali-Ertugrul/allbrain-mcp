"""Domain module: intents."""

from __future__ import annotations

import logging
from typing import Any

from allbrain.domains.analysis.contradiction.detector import ContradictionDetector
from allbrain.domains.reasoning.intent.extractor import IntentExtractor
from allbrain.models.schemas import (
    IntentInput,
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
def extract_intents_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = IntentInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
    bound_session_id = bind_session_id(context, None)
    events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
    intents = IntentExtractor().extract(events)
    audit_tool_call(
        context,
        tool_name="extract_intents",
        tool_args={"limit": data.limit},
        session_id=bound_session_id,
    )
    return ToolResult(
        ok=True, data={"intents": [intent.model_dump(mode="json") for intent in intents], "count": len(intents)}
    )


@handle_tool_errors
def detect_contradictions_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    data = IntentInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
    bound_session_id = bind_session_id(context, None)
    events = context.repository.list_events(project_path=context.project_path, limit=data.limit)
    intents = IntentExtractor().extract(events)
    contradictions = ContradictionDetector().detect(intents)
    audit_tool_call(
        context,
        tool_name="detect_contradictions",
        tool_args={"limit": data.limit},
        session_id=bound_session_id,
    )
    return ToolResult(ok=True, data={"contradictions": contradictions, "count": len(contradictions)})


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def extract_intents(limit: int = 5000) -> dict[str, Any]:
        """Extract semantic intents from agent actions in the event log.

        Use this to understand what goals, constraints, and decisions agents were
        pursuing. Intents are extracted from events like TASK_CREATED, TOOL_CALLED,
        and DECISION_MADE.

        Side effects: Read-only operation; analyzes events without modification.

        Args:
            limit: Maximum number of events to analyze (default 5000).

        Returns:
            List of extracted intents with goal, constraints, and context from each
            agent's actions.
        """
        result = extract_intents_impl(context, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def detect_contradictions(limit: int = 5000) -> dict[str, Any]:
        """Identify logical contradictions in extracted agent intents.

        Use this to find when agents have contradictory goals, constraints, or
        decisions. Unlike `detect_conflicts` (which finds conflicting outputs),
        this finds logical inconsistencies in what agents were trying to achieve.

        Use `detect_conflicts` for semantic state contradictions between agents.

        Side effects: Read-only operation; analyzes extracted intents.

        Args:
            limit: Maximum number of events to analyze (default 5000).

        Returns:
            List of detected contradictions with the conflicting intent elements,
            agent IDs involved, and suggested resolutions.
        """
        result = detect_contradictions_impl(context, limit=limit)
        return result.model_dump(mode="json")
