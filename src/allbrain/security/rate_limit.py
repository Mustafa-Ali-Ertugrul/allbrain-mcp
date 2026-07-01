from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any


class RateLimitError(ValueError):
    """Raised when a rate limit is exceeded."""


class SlidingWindowCounter:
    """Per-key sliding-window rate limiter.

    Tracks events in a fixed number of buckets over a rolling window.
    If the total count in the window exceeds *max_events*, the key is
    temporarily denied until the window slides past the oldest events.

    Thread-safe — all public methods are protected by a per-instance lock.
    Uses ``collections.deque`` for O(expired) prune via ``popleft``.
    """

    def __init__(self, window_seconds: float, max_events: int, buckets: int = 10) -> None:
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self._lock = threading.Lock()
        self._window = window_seconds
        self._max = max_events
        self._bucket_span = window_seconds / buckets
        self._buckets: dict[str, deque[float]] = {}  # key → deque of timestamps

    def _prune(self, key: str, now: float) -> None:
        ts_list = self._buckets.get(key)
        if ts_list is None:
            return
        cutoff = now - self._window
        # Pop expired timestamps from the front (O(expired_count))
        while ts_list and ts_list[0] <= cutoff:
            ts_list.popleft()
        if not ts_list:
            self._buckets.pop(key, None)

    def check(self, key: str) -> tuple[bool, int]:
        """Return ``(allowed, current_count)`` without recording the call."""
        with self._lock:
            now = time.monotonic()
            self._prune(key, now)
            cur = len(self._buckets.get(key, deque()))
            return cur < self._max, cur

    def record(self, key: str) -> None:
        """Record one call for *key*."""
        with self._lock:
            now = time.monotonic()
            self._prune(key, now)
            self._buckets.setdefault(key, deque()).append(now)

    def check_and_record(self, key: str) -> tuple[bool, int]:
        """Atomic check-and-record.  Returns ``(allowed, current_count)``."""
        with self._lock:
            now = time.monotonic()
            self._prune(key, now)
            ts_list = self._buckets.get(key, deque())
            cur = len(ts_list)
            if cur >= self._max:
                return False, cur
            ts_list.append(now)
            self._buckets[key] = ts_list
            return True, cur + 1

    def reset(self, key: str | None = None) -> None:
        """Clear history for one key, or all keys."""
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)


# Rate limit defaults (generous — catch runaway loops, not normal usage).
# Override via env vars:
#   ALLBRAIN_RATE_LIMIT_RPM   — requests per minute  (default 100000)
#   ALLBRAIN_RATE_LIMIT_RPS   — requests per second  (default 1000)
_DEFAULT_RPM = int(os.environ.get("ALLBRAIN_RATE_LIMIT_RPM", "100000"))
_DEFAULT_RPS = int(os.environ.get("ALLBRAIN_RATE_LIMIT_RPS", "1000"))

_MINUTE_LIMITER = SlidingWindowCounter(window_seconds=60.0, max_events=_DEFAULT_RPM)
_BURST_LIMITER = SlidingWindowCounter(window_seconds=1.0, max_events=_DEFAULT_RPS)

_TOOL_MINUTE_RPS = _DEFAULT_RPM
_TOOL_BURST_RPS = _DEFAULT_RPS


def reset_rate_limits() -> None:
    """Clear all rate-limit counters.  Useful in test teardown."""
    _MINUTE_LIMITER.reset()
    _BURST_LIMITER.reset()


def check_tool_rate(tool_name: str) -> None:
    """Check both minute and burst limits for *tool_name*.

    Checks the burst (1-second) window first so that fast-fail is
    cheaper.  Rolls back burst records when the minute window is
    full.  Raises ``RateLimitError`` if either limit is exceeded.
    Call once per tool invocation.
    """
    burst_ok, burst_count = _BURST_LIMITER.check_and_record(tool_name)
    if not burst_ok:
        raise RateLimitError(f"Rate limit exceeded for '{tool_name}': {burst_count}/{_TOOL_BURST_RPS} per second")

    minute_ok, minute_count = _MINUTE_LIMITER.check_and_record(tool_name)
    if not minute_ok:
        _BURST_LIMITER.reset(tool_name)
        raise RateLimitError(f"Rate limit exceeded for '{tool_name}': {minute_count}/{_TOOL_MINUTE_RPS} per minute")
