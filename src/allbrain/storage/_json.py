"""Fast JSON (de)serialization with orjson fallback.

orjson is ~3-5x faster than the stdlib json module for the small-to-medium
payloads AllBrain persists on the event-sourced write path
(``repository.append_event``, ``queueing.enqueue_task``). We keep a stdlib
fallback so the package still imports on environments where orjson cannot be
installed (e.g. unusual platforms).
"""

from __future__ import annotations

from typing import Any

try:
    import orjson

    _HAS_ORJSON = True
except ImportError:  # pragma: no cover - orjson is a hard dependency
    import json

    _HAS_ORJSON = False


def dumps(payload: Any) -> str:
    """Serialize *payload* to a canonical JSON string (sorted keys, ASCII)."""
    if _HAS_ORJSON:
        return orjson.dumps(
            payload,
            default=str,
            option=orjson.OPT_SORT_KEYS | orjson.OPT_NON_STR_KEYS | orjson.OPT_OMIT_MICROSECONDS,
        ).decode("utf-8")
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)


def loads(value: str) -> Any:
    """Parse a JSON string produced by :func:`dumps`."""
    if _HAS_ORJSON:
        return orjson.loads(value)
    return json.loads(value)
