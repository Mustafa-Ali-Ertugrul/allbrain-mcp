"""Shared decorators for MCP tool implementations."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from allbrain.models.schemas import ToolResult, UserInputError
from allbrain.security.redaction import sanitize_text, sanitize_valerr_msg

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
        except ValueError:
            logger.exception("Tool rejected an unexpected value")
            return ToolResult(ok=False, error="Internal server error", error_code="internal_error")
        except Exception:
            logger.exception("Tool failed")
            return ToolResult(ok=False, error="Internal server error", error_code="internal_error")

    return wrapper
