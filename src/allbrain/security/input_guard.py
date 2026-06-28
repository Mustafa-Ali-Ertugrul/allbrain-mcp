"""Input sanitization for the MCP boundary.

Expanded version of the prompt-injection patterns from agents/safety.py.
Applied at the BaseInputModel level in schemas.py so all MCP tools are
protected without importing the heavy agents/ dependency tree.

NOTE: This module has diverged from ``agents/safety.py`` (6 patterns here
vs 14 there).  The two lists should be consolidated in a shared security
policy to prevent future drift.
"""

from __future__ import annotations

import re
from typing import Any

# Core patterns from agents/safety.py — duplicated here to avoid
# circular dependency on allbrain.agents.* in server/app.py.
_SUSPICIOUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(previous|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
    re.compile(r"</?\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*script\s*>", re.IGNORECASE),
    re.compile(r"(?i)drop\s+table"),
    re.compile(r"(?i)rm\s+-rf\s+/"),
    # Expanded patterns
    re.compile(r"disregard\s+(previous|above|all)\s+(instructions?|guidelines?)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:if\s+(?:you\s+(?:are|were)\s+)?)?(?:a|an|the)\b", re.IGNORECASE),
    re.compile(r"pretend\s+(to\s+be|that\s+you(\u2019|')re)\s+(a|an)", re.IGNORECASE),
    re.compile(r"</?\s*(user|assistant|tool|function)\s*>", re.IGNORECASE),
    re.compile(r"from\s+now\s+on\s*,?\s*you\s+(will|are|must|should)", re.IGNORECASE),
    re.compile(r"override\s+(?:all\s+)?(?:previous\s+)?(?:instructions?|directives?)", re.IGNORECASE),
]

_MASK = "[REDACTED]"


def sanitize_user_text(text: str) -> str:
    """Remove suspicious patterns from user-supplied text.

    Preserves the original for non-string types.
    Applied to all str fields in BaseInputModel subclasses.
    """
    if not isinstance(text, str):
        return text
    cleaned = text
    for pattern in _SUSPICIOUS_PATTERNS:
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
