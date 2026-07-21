from __future__ import annotations

from typing import Any


def clamp(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = default
    return round(max(0.0, min(numeric, 1.0)), 6)


def autonomy_level(value: Any, default: int = 0) -> int:
    if isinstance(value, str) and value.upper().startswith("L"):
        value = value[1:]
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = default
    return max(0, min(numeric, 5))


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))
