"""Shared prompt-injection rule patterns — single source of truth.

Used by both ``security/input_guard.py`` (MCP boundary) and
``agents/safety.py`` (agent-execution boundary) so the two layers
cannot drift apart.
"""

from __future__ import annotations

import re

# 14 compiled regex patterns for prompt-injection detection.
# These are the expanded set: the original 6 core patterns plus 8
# additional ones added during the security-hardening sprint.
PROMPT_INJECTION_PATTERNS: list[re.Pattern] = [
    # --- Core (originally from agents/safety.py) ---
    re.compile(r"ignore\s+(previous|all)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are\s+now", re.IGNORECASE),
    re.compile(r"</?\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*script\s*>", re.IGNORECASE),
    re.compile(r"(?i)drop\s+table"),
    re.compile(r"(?i)rm\s+-rf\s+/"),
    # --- Expanded (added in security/input_guard.py) ---
    re.compile(
        r"disregard\s+(previous|above|all)\s+(instructions?|guidelines?)",
        re.IGNORECASE,
    ),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(
        r"act\s+as\s+(?:if\s+(?:you\s+(?:are|were)\s+)?)?(?:a|an|the)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"pretend\s+(to\s+be|that\s+you(\u2019|')re)\s+(a|an)",
        re.IGNORECASE,
    ),
    re.compile(r"</?\s*(user|assistant|tool|function)\s*>", re.IGNORECASE),
    re.compile(
        r"from\s+now\s+on\s*,?\s*you\s+(will|are|must|should)",
        re.IGNORECASE,
    ),
    re.compile(
        r"override\s+(?:all\s+)?(?:previous\s+)?(?:instructions?|directives?)",
        re.IGNORECASE,
    ),
]
