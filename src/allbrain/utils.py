"""General-purpose utilities used across the allbrain codebase."""

from __future__ import annotations

from datetime import UTC, datetime


def as_utc[T: datetime | None](dt: T) -> T:
    """Ensure a datetime is timezone-aware with ``UTC`` tzinfo.

    Returns ``None`` unchanged, preserves already-aware datetimes,
    and attaches ``UTC`` to naive datetimes.

    Usage::

        from allbrain.utils import as_utc

        dt = as_utc(datetime.now())        # → datetime(…, tzinfo=UTC)
        dt = as_utc(datetime.now(UTC))     # → same object
        dt = as_utc(None)                  # → None
    """
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
