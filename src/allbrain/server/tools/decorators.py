"""Shared decorators for MCP tool implementations."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from allbrain.models.schemas import ToolResult, UserInputError
from allbrain.security.redaction import sanitize_text, sanitize_valerr_msg

try:
    from fastmcp.exceptions import ToolError
except ImportError:  # pragma: no cover - FastMCP always present at runtime
    ToolError = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def handle_tool_errors(func: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
    """Standardize error handling for all MCP tool implementations.

    Catches common exceptions and converts them to ToolResult with
    appropriate error messages. Sanitizes ValidationError messages
    to prevent information leakage.

    Usage:
        @handle_tool_errors
        def my_tool_impl(context: BrainContext, **kwargs) -> ToolResult:
            # ... implementation ...
            return ToolResult(ok=True, data=result)

    Returns:
        Decorated function that wraps errors in ToolResult.

    Note:
        This sync variant preserves the existing ToolResult contract used
        across all 17 domain modules and their tests. For new async tools
        (see Faz 2 migration) prefer ``handle_tool_errors_mcp`` which maps
        unexpected failures onto FastMCP's ``ToolError`` so the MCP client
        receives a proper ``isError: true`` envelope.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            return ToolResult(
                ok=False,
                error=sanitize_valerr_msg(str(exc)),
                error_code="validation_error",
            )
        except UserInputError as exc:
            return ToolResult(
                ok=False,
                error=sanitize_text(str(exc)),
                error_code="user_input_error",
            )
        except Exception:
            logger.exception("Tool failed")
            return ToolResult(ok=False, error="Internal server error", error_code="internal_error")

    return wrapper


def handle_tool_errors_mcp(func: Callable[..., Any]) -> Callable[..., Any]:
    """Async-safe MCP envelope decorator.

    Maps tool failures onto the correct MCP representation:

    * ``ValidationError`` → masked ``ToolResult`` (client-facing, no leak)
    * ``UserInputError``  → masked ``ToolResult`` (client-facing)
    * any other ``Exception`` → raises ``fastmcp.exceptions.ToolError`` so the
      MCP server emits a proper ``CallToolResult(isError=True, ...)`` envelope
      instead of silently swallowing the traceback into ``{"ok": false}``.

    Works for both ``sync`` and ``async`` tool implementations. When the
    wrapped function is a coroutine, the decorator awaits it inside the
    try/except so cancellation and exceptions are captured uniformly.
    """

    @functools.wraps(func)
    def _invoke(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    if _is_coroutine(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> ToolResult:
            try:
                return await func(*args, **kwargs)
            except ValidationError as exc:
                return ToolResult(
                    ok=False,
                    error=sanitize_valerr_msg(str(exc)),
                    error_code="validation_error",
                )
            except UserInputError as exc:
                return ToolResult(
                    ok=False,
                    error=sanitize_text(str(exc)),
                    error_code="user_input_error",
                )
            except Exception:
                logger.exception("Tool failed: %s", getattr(func, "__name__", "?"))
                if ToolError is not None:
                    raise ToolError("Internal server error") from None
                raise

        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> ToolResult:
        try:
            return func(*args, **kwargs)
        except ValidationError as exc:
            return ToolResult(
                ok=False,
                error=sanitize_valerr_msg(str(exc)),
                error_code="validation_error",
            )
        except UserInputError as exc:
            return ToolResult(
                ok=False,
                error=sanitize_text(str(exc)),
                error_code="user_input_error",
            )
        except Exception:
            logger.exception("Tool failed: %s", getattr(func, "__name__", "?"))
            if ToolError is not None:
                raise ToolError("Internal server error") from None
            raise

    return sync_wrapper


def _is_coroutine(func: Callable[..., Any]) -> bool:
    import asyncio

    return asyncio.iscoroutinefunction(func)
