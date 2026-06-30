"""Domain module: intents."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.contradiction.detector import ContradictionDetector
from allbrain.intent.extractor import IntentExtractor
from allbrain.models.schemas import (
    IntentInput,
    ToolResult,
    UserInputError,
)
from allbrain.security.redaction import sanitize_valerr_msg
from allbrain.server.context import BrainContext
from allbrain.server.tools._shared import (
    audit_tool_call,
    bind_session_id,
)

logger = logging.getLogger(__name__)


def extract_intents_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = IntentInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
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
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def detect_contradictions_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        data = IntentInput.model_validate({"include_git": True, "use_snapshot": True, **kwargs})
        bound_session_id = bind_session_id(context, None)
        project_path = context.project_path
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
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def extract_intents(limit: int = 5000) -> dict[str, Any]:
        result = extract_intents_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def detect_contradictions(limit: int = 5000) -> dict[str, Any]:
        result = detect_contradictions_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")
