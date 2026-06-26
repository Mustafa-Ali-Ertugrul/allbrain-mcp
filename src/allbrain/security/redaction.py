from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "openai"),
    (re.compile(r"sk-[a-zA-Z0-9]{32,}"), "anthropic"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "github_pat"),
    (re.compile(r"gho_[a-zA-Z0-9]{36}"), "github_oauth"),
    (re.compile(r"ghu_[a-zA-Z0-9]{36}"), "github_user"),
    (re.compile(r"ghr_[a-zA-Z0-9]{36}"), "github_refresh"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws_access_key"),
    (re.compile(r"xox[baprs]-[a-zA-Z0-9-]+"), "slack_token"),
]

MASK = "********"


def sanitize_payload(payload: Any) -> Any:
    """Recursively walk a payload and mask known secret patterns.

    The actual secret values are **never** logged — only a summary
    of how many redactions occurred and which types were found.

    Returns the sanitised copy (original is not mutated).
    """
    found_types: dict[str, int] = {}

    def _walk(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_walk(v) for v in obj]
        if isinstance(obj, str):
            for pattern, secret_type in SECRET_PATTERNS:
                match = pattern.search(obj)
                if match:
                    found_types[secret_type] = found_types.get(secret_type, 0) + 1
                    obj = pattern.sub(MASK, obj)
            return obj
        return obj

    result = _walk(payload)
    if found_types:
        logger.info(
            "secret_redacted",
            extra={
                "count": sum(found_types.values()),
                "types": sorted(found_types.keys()),
            },
        )
    return result
