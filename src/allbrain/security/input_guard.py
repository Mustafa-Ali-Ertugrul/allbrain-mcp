"""Input sanitization for the MCP boundary.

Applied at the BaseInputModel level in schemas.py so all MCP tools are
protected without importing the heavy agents/ dependency tree.

Patterns are shared from ``allbrain.security._prompt_rules``.
"""

from __future__ import annotations

import os
from typing import Any

from allbrain.security._prompt_rules import PROMPT_INJECTION_PATTERNS

_MASK = "[REDACTED]"


def _get_max_input_guard_depth() -> int:
    """Read max input guard depth from env (ALLBRAIN_INPUT_GUARD_MAX_DEPTH), default 32.

    Bounds-checked to [1, 256] to prevent misconfiguration DoS.
    """
    raw = os.environ.get("ALLBRAIN_INPUT_GUARD_MAX_DEPTH", "").strip()
    if not raw:
        return 32
    try:
        val = int(raw)
    except ValueError:
        return 32
    return max(1, min(256, val))


_MAX_INPUT_GUARD_DEPTH = _get_max_input_guard_depth()


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
    """Recursively sanitize string values in a dict payload (depth-limited).

    Depth is bounded by ``_MAX_INPUT_GUARD_DEPTH`` (env:
    ``ALLBRAIN_INPUT_GUARD_MAX_DEPTH``, default 32). At the boundary the
    subtree is returned un-modified (fail-open for sanitization only — null-
    byte checking is handled separately and raises on overflow).
    """
    return _sanitize_payload_fields_impl(payload, depth=0)


def _sanitize_payload_fields_impl(payload: dict[str, Any], *, depth: int) -> dict[str, Any]:
    if depth >= _MAX_INPUT_GUARD_DEPTH:
        return dict(payload)
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            out[key] = sanitize_user_text(value)
        elif isinstance(value, dict):
            out[key] = _sanitize_payload_fields_impl(value, depth=depth + 1)
        elif isinstance(value, list):
            out[key] = [
                _sanitize_payload_fields_impl(v, depth=depth + 1)
                if isinstance(v, dict)
                else sanitize_user_text(v)
                if isinstance(v, str)
                else v
                for v in value
            ]
        else:
            out[key] = value
    return out
