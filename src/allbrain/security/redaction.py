from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}", re.IGNORECASE), "anthropic"),
    (re.compile(r"sk-(?!ant-)[a-zA-Z0-9]{20,}", re.IGNORECASE), "openai"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE), "github_pat"),
    (re.compile(r"gho_[a-zA-Z0-9]{36}", re.IGNORECASE), "github_oauth"),
    (re.compile(r"ghu_[a-zA-Z0-9]{36}", re.IGNORECASE), "github_user"),
    (re.compile(r"ghr_[a-zA-Z0-9]{36}", re.IGNORECASE), "github_refresh"),
    (re.compile(r"ghs_[a-zA-Z0-9]{36}", re.IGNORECASE), "github_server_to_server"),
    (re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE), "aws_access_key"),
    (re.compile(r"xox[baprs]-[a-zA-Z0-9-]+", re.IGNORECASE), "slack_token"),
    # Extended patterns
    (re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"), "jwt"),
    (
        re.compile(
            r"-----BEGIN (?:OPENSSH|RSA|EC|DSA|PGP) PRIVATE KEY-----"
            r"[A-Za-z0-9+/=\s]*?"
            r"-----END (?:OPENSSH|RSA|EC|DSA|PGP) ?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
        "ssh_private_key",
    ),
    (re.compile(r"(?:sk|rk)_(?:live|test)_[a-zA-Z0-9]{20,}"), "stripe"),
    (re.compile(r"\bAC[a-fA-F0-9]{32}\b", re.IGNORECASE), "twilio"),
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "google_api_key"),
]

# Dict key substrings that indicate sensitive values.
# Any value under a matching key is masked entirely.
# Uses exact name matching only — suffix matching was too aggressive
# (e.g. metric_key, foreign_key, task_key are not secrets).
_SENSITIVE_FIELD_NAMES: set[str] = {
    "secret",
    "password",
    "credential",
    "api_key",
    "api_secret",
    "access_key",
    "access_token",
    "secret_key",
    "private_key",
    "auth_token",
    "refresh_token",
    "apikey",
    "bearer",
    "client_secret",
    "authorization",
    "password_hash",
}

MASK = "********"


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return lower in _SENSITIVE_FIELD_NAMES


def _sanitize_payload_impl(obj: Any, found_types: dict[str, int]) -> Any:
    """Core recursive walk with field-name redaction."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and _is_sensitive_key(k):
                found_types["field_name"] = found_types.get("field_name", 0) + 1
                out[k] = MASK
            elif isinstance(v, str):
                out[k] = _mask_secrets(v, found_types)
            else:
                out[k] = _sanitize_payload_impl(v, found_types)
        return out
    if isinstance(obj, list):
        return [_sanitize_payload_impl(v, found_types) for v in obj]
    if isinstance(obj, str):
        return _mask_secrets(obj, found_types)
    return obj


def _mask_secrets(text: str, found_types: dict[str, int]) -> str:
    """Apply SECRET_PATTERNS to a single string."""
    for pattern, secret_type in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            found_types[secret_type] = found_types.get(secret_type, 0) + 1
            text = pattern.sub(MASK, text)
    return text


def sanitize_text(text: str) -> str:
    """Sanitize a single string by masking known secret patterns.

    Returns the text with secret patterns replaced by ``MASK``.
    Intended for use on free-form text such as git command output,
    log messages, or AI-generated content.
    """
    found_types: dict[str, int] = {}
    result = _mask_secrets(text, found_types)
    if found_types:
        logger.info(
            "secret_redacted",
            extra={
                "count": sum(found_types.values()),
                "types": sorted(found_types.keys()),
            },
        )
    return result


# Pattern to strip ``input=...`` from Pydantic ValidationError detail lines
# without losing the error type / location.  Example match:
#   "Input should be a valid string [type=string_type, input_value='sk-abc...', input_type=str]"
#   → "Input should be a valid string [type=string_type, input_type=str]"
_PYDANTIC_INPUT_RE = re.compile(r",?\s*input_value=(?:[^,\]]|,(?!\s*\w+=))*")


def sanitize_valerr_msg(msg: str) -> str:
    """Strip user-supplied input values from a Pydantic ``ValidationError`` message.

    Removes ``input_value=...`` fragments, then runs the result through
    ``sanitize_text`` so that any remaining secret patterns are also masked.
    """
    cleaned = _PYDANTIC_INPUT_RE.sub("", msg)
    return sanitize_text(cleaned)


def sanitize_payload(payload: Any) -> Any:
    """Recursively walk a payload and mask known secret patterns.

    Also masks entire values under dict keys whose names match
    sensitive field names (e.g. ``{\"api_key\": \"sk-...\"}`` → value
    masked regardless of content).

    The actual secret values are **never** logged — only a summary
    of how many redactions occurred and which types were found.

    Returns the sanitised copy (original is not mutated).
    """
    found_types: dict[str, int] = {}
    result = _sanitize_payload_impl(payload, found_types)
    if found_types:
        logger.info(
            "secret_redacted",
            extra={
                "count": sum(found_types.values()),
                "types": sorted(found_types.keys()),
            },
        )
    return result
