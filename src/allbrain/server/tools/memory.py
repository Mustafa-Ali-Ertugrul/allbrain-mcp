"""Domain module: memory."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from allbrain.memory import MemoryBuilder, MemoryRetriever, WorkflowMemoryStore
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

logger = logging.getLogger(__name__)


def build_memory_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        project_path, limit = observability_project_and_limit(context, kwargs)
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        store = WorkflowMemoryStore(MemoryBuilder().build(events))
        audit_tool_call(
            context,
            tool_name="build_memory",
            tool_args={"limit": limit},
            session_id=bound_session_id,
        )
        return ToolResult(ok=True, data=store.to_dict())
    except ValidationError as exc:
        return ToolResult(ok=False, error=sanitize_valerr_msg(str(exc)))
    except UserInputError as exc:
        return ToolResult(ok=False, error=str(exc))
    except Exception:
        logger.exception("Tool failed")
        return ToolResult(ok=False, error="Internal server error")


def retrieve_memory_impl(context: BrainContext, **kwargs: Any) -> ToolResult:
    try:
        query = kwargs.get("query")
        if not isinstance(query, str) or not query:
            raise UserInputError("query is required")
        project_path, limit = observability_project_and_limit(context, kwargs)
        top_k = int(kwargs.get("top_k", 5) or 5)
        if top_k < 1 or top_k > 50:
            raise UserInputError("top_k must be between 1 and 50")
        bound_session_id = bind_session_id(context, None)
        events = context.repository.list_events(project_path=context.project_path, limit=limit)
        retriever = MemoryRetriever(MemoryBuilder().build(events))
        result = {
            "similar_workflows": retriever.retrieve_similar_workflows(query, top_k=top_k),
            "failure_patterns": retriever.retrieve_failure_patterns(query, top_k=top_k),
        }
        audit_tool_call(
            context,
            tool_name="retrieve_memory",
            tool_args={"query": query, "limit": limit, "top_k": top_k},
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


def register_tools(mcp, context: BrainContext) -> None:
    @mcp.tool
    def build_memory(limit: int = 5000) -> dict[str, Any]:
        """Build a semantic memory index from project events.

        Args:
            limit: Maximum number of events to index (default 5000).

        Returns:
            Tool result as a JSON-serializable dict.
        """
        result = build_memory_impl(context, project_path=context.project_path, limit=limit)
        return result.model_dump(mode="json")

    @mcp.tool
    def retrieve_memory(
        query: str,
        limit: int = 5000,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Semantic search over stored memories.

        Args:
            query: Search query string.
            limit: Maximum number of events to scan (default 5000).
            top_k: Number of top results to return (default 5).

        Returns:
            Tool result as a JSON-serializable dict.
        """
        result = retrieve_memory_impl(context, query=query, project_path=context.project_path, limit=limit, top_k=top_k)
        return result.model_dump(mode="json")
