"""Shared prompt-injection rule patterns — single source of truth.

Used by both ``security/input_guard.py`` (MCP boundary) and
``agents/safety.py`` (agent-execution boundary) so the two layers
cannot drift apart.
"""

from __future__ import annotations

import re

# 22 compiled regex patterns for prompt-injection detection.
# These are the expanded set: the original 6 core patterns plus 8
# additional ones added during the security-hardening sprint, plus the
# 8 Phase-F patterns (JSON-embedded directives, continuation attacks,
# fake role markers, markdown system-directives, theory-of-mind coercion,
# encoded-payload smuggling, developer impersonation, tooling
# impersonation).
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
    # --- Phase F: JSON-embedded directives ---
    re.compile(r"[\"'](?:system_prompt|instructions)[\"']\s*:", re.IGNORECASE),
    # --- Phase F: continuation attacks ---
    re.compile(
        r"ignore\s+all\s+(?:prior|previous|above)\s+(?:context|instructions?|prompts?)",
        re.IGNORECASE,
    ),
    # --- Phase F: role impersonation ("as the system/developer ...") ---
    re.compile(r"as\s+the\s+(?:system|developer|assistant|model)\b", re.IGNORECASE),
    # --- Phase F: comment-style escape ("// ignore above ...") ---
    re.compile(r"//\s*(?:ignore|disregard)\s+(?:above|all|everything|previous)", re.IGNORECASE),
    # --- Phase F: fake bracketed role markers ("[System] you must ...") ---
    re.compile(
        r"\[\s*(?:system|developer|user|assistant|admin)\s*\]\s*(?:you|please|must|now)\b",
        re.IGNORECASE,
    ),
    # --- Phase F: markdown-quoted system directive ("> system: You must ...") ---
    re.compile(r">\s*system\s*:\s*you\s+must", re.IGNORECASE),
    # --- Phase F: theory-of-mind coercion ("Actually, you must ...") ---
    re.compile(r"actually\s*,?\s*you\s+must", re.IGNORECASE),
    # --- Phase F: meta-instruction disclosure (real instructions / true objective) ---
    re.compile(
        r"(?:tell|show|reveal|share)\s+(?:me|us)\s+(?:your|the)\s+(?:real|actual|true)\s+instructions?"
        r"|what\s+you\s+(?:were|are)\s+(?:really|actually)\s+(?:instructed|told)"
        r"|your\s+(?:true|real|actual)\s+objective",
        re.IGNORECASE,
    ),
]
