"""Input sanitization for the MCP boundary.

Applied at the BaseInputModel level in schemas.py so all MCP tools are
protected without importing the heavy agents/ dependency tree.

Patterns are shared from ``allbrain.security._prompt_rules``.
"""

from __future__ import annotations

from typing import Any

from allbrain.security._prompt_rules import PROMPT_INJECTION_PATTERNS

_MASK = "[REDACTED]"


def sanitize_user_text(text: str) -> str:
    """Remove suspicious patterns from user-supplied text.

    Preserves the original for non-string types.
    Applied to all str fields in BaseInputModel subclasses.
    """
    if not isinstance(text, str):
        return text
    cleaned = text
    for pattern in PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub(_MASK, cleaned)
    return cleaned


def sanitize_payload_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize string values in a dict payload."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            out[key] = sanitize_user_text(value)
        elif isinstance(value, dict):
            out[key] = sanitize_payload_fields(value)
        elif isinstance(value, list):
            out[key] = [
                sanitize_payload_fields(v) if isinstance(v, dict)
                else sanitize_user_text(v) if isinstance(v, str)
                else v
                for v in value
            ]
        else:
            out[key] = value
    return out
