from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

_MAX_ENV_PATTERN_LENGTH = 512
_MAX_SANITIZE_DEPTH = 32

_BUILTIN_SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}", re.IGNORECASE), "anthropic"),
    (re.compile(r"sk-(?!ant-)[a-zA-Z0-9]{40,}", re.IGNORECASE), "openai"),
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


def _load_env_secret_patterns() -> list[tuple[re.Pattern, str]]:
    """Load optional extra patterns from ALLBRAIN_SECRET_PATTERNS_JSON."""
    raw = os.environ.get("ALLBRAIN_SECRET_PATTERNS_JSON", "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("ALLBRAIN_SECRET_PATTERNS_JSON is not valid JSON; ignoring")
        return []
    if not isinstance(payload, list):
        logger.warning("ALLBRAIN_SECRET_PATTERNS_JSON must be a JSON list; ignoring")
        return []
    loaded: list[tuple[re.Pattern, str]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            logger.warning("ALLBRAIN_SECRET_PATTERNS_JSON[%s] must be an object; skipping", index)
            continue
        pattern = item.get("pattern")
        name = item.get("name") or f"env_pattern_{index}"
        if not isinstance(pattern, str) or not pattern:
            logger.warning("ALLBRAIN_SECRET_PATTERNS_JSON[%s] missing pattern; skipping", index)
            continue
        if len(pattern) > _MAX_ENV_PATTERN_LENGTH:
            logger.warning(
                "ALLBRAIN_SECRET_PATTERNS_JSON[%s] pattern exceeds %s chars; skipping",
                index,
                _MAX_ENV_PATTERN_LENGTH,
            )
            continue
        if not isinstance(name, str) or not name:
            name = f"env_pattern_{index}"
        try:
            loaded.append((re.compile(pattern), name))
        except re.error as exc:
            logger.warning(
                "ALLBRAIN_SECRET_PATTERNS_JSON[%s] invalid regex (%s); skipping",
                index,
                exc,
            )
    return loaded


SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    *_BUILTIN_SECRET_PATTERNS,
    *_load_env_secret_patterns(),
]


def reload_secret_patterns() -> None:
    """Rebuild SECRET_PATTERNS from builtins + current env (for tests)."""
    SECRET_PATTERNS[:] = [*_BUILTIN_SECRET_PATTERNS, *_load_env_secret_patterns()]


# Dict key names that indicate sensitive values (after normalization).
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
    "proxy_authorization",
    "x_api_key",
    "x_auth_token",
}

# Query/header bare names that are sensitive as params but too broad as JSON fields
# (e.g. pagination ``token`` values should not wipe entire objects).
_SENSITIVE_QUERY_NAMES: set[str] = _SENSITIVE_FIELD_NAMES | {
    "token",
    "auth",
    "signature",
    "sig",
}

# Normalized keys that end with these suffixes are treated as sensitive
# (token-boundary style: my_password, user_secret, app_api_key).
_SENSITIVE_SUFFIXES: tuple[str, ...] = (
    "_password",
    "_secret",
    "_token",
    "_api_key",
    "_access_key",
    "_private_key",
    "_auth_token",
    "_refresh_token",
    "_client_secret",
)

# Exact normalized names that look suffix-sensitive but are not secrets.
_SAFE_KEY_DENYLIST: set[str] = {
    "task_key",
    "foreign_key",
    "metric_key",
    "primary_key",
    "public_key",
    "keyboard",
    "key",
    "keys",
}

MASK = "********"

# URL-ish strings: scheme:// or query with =
_URLISH_RE = re.compile(r"(?:[a-zA-Z][a-zA-Z0-9+.-]*://|[?&][^=\s]+=)")


def _normalize_key(key: str) -> str:
    """Lowercase and map separators so header/query variants match field rules."""
    lowered = key.strip().lower()
    return re.sub(r"[-.\s]+", "_", lowered)


def _is_sensitive_key(key: str, *, for_query: bool = False) -> bool:
    if not isinstance(key, str) or not key:
        return False
    normalized = _normalize_key(key)
    if normalized in _SAFE_KEY_DENYLIST:
        return False
    names = _SENSITIVE_QUERY_NAMES if for_query else _SENSITIVE_FIELD_NAMES
    if normalized in names:
        return True
    # Strip common header prefixes after normalize (x-api-key → x_api_key already).
    if normalized.startswith("x_") and normalized[2:] in _SENSITIVE_FIELD_NAMES:
        return True
    return any(normalized.endswith(suffix) and normalized not in _SAFE_KEY_DENYLIST for suffix in _SENSITIVE_SUFFIXES)


def _mask_query_string(query: str, found_types: dict[str, int]) -> str:
    if not query:
        return query
    pairs = parse_qsl(query, keep_blank_values=True)
    changed = False
    out: list[tuple[str, str]] = []
    for name, value in pairs:
        if _is_sensitive_key(name, for_query=True):
            found_types["query_param"] = found_types.get("query_param", 0) + 1
            out.append((name, MASK))
            changed = True
        else:
            masked_value = _mask_secrets_patterns(value, found_types)
            if masked_value != value:
                changed = True
            out.append((name, masked_value))
    # Keep * unescaped so MASK stays readable in logs/tests.
    return urlencode(out, doseq=True, safe="*") if changed else query


def _mask_url_or_text(text: str, found_types: dict[str, int]) -> str:
    """Mask sensitive query params in URL-like strings, then pattern-mask."""
    # Fast path: most event payloads are short non-URL strings.
    if not text or ("?" not in text and "://" not in text and "&" not in text):
        return _mask_secrets_patterns(text, found_types)
    if not _URLISH_RE.search(text):
        return _mask_secrets_patterns(text, found_types)

    # Full URL
    if "://" in text or text.startswith("//"):
        parts = urlsplit(text)
        if parts.query:
            new_query = _mask_query_string(parts.query, found_types)
            if new_query != parts.query:
                text = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
        return _mask_secrets_patterns(text, found_types)

    # Bare query string or path?query
    if "?" in text:
        path, _, query = text.partition("?")
        frag = ""
        if "#" in query:
            query, _, frag = query.partition("#")
            frag = "#" + frag
        new_query = _mask_query_string(query, found_types)
        text = f"{path}?{new_query}{frag}"
    return _mask_secrets_patterns(text, found_types)


def _mask_secrets_patterns(text: str, found_types: dict[str, int]) -> str:
    for pattern, secret_type in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            found_types[secret_type] = found_types.get(secret_type, 0) + 1
            text = pattern.sub(MASK, text)
    return text


def _sanitize_payload_impl(
    obj: Any, found_types: dict[str, int], *, depth: int = 0
) -> Any:
    """Core recursive walk with field-name redaction."""
    if depth >= _MAX_SANITIZE_DEPTH:
        return obj
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and _is_sensitive_key(k):
                found_types["field_name"] = found_types.get("field_name", 0) + 1
                out[k] = MASK
            elif isinstance(v, str):
                out[k] = _mask_url_or_text(v, found_types)
            else:
                out[k] = _sanitize_payload_impl(v, found_types, depth=depth + 1)
        return out
    if isinstance(obj, list):
        return [_sanitize_payload_impl(v, found_types, depth=depth + 1) for v in obj]
    if isinstance(obj, str):
        return _mask_url_or_text(obj, found_types)
    return obj


def _mask_secrets(text: str, found_types: dict[str, int]) -> str:
    """Apply URL-aware then pattern masking to a single string."""
    return _mask_url_or_text(text, found_types)


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
_PYDANTIC_INPUT_RE = re.compile(r",?\s*input_value=(?:(?!,\s*\w+=|\])[^]])*")


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
