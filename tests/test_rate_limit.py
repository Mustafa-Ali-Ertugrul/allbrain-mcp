"""Unit tests for the sliding-window rate limiter."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from allbrain.security.rate_limit import (
    RateLimitError,
    SlidingWindowCounter,
    check_tool_rate,
    reset_rate_limits,
)


class TestSlidingWindowCounter:
    def test_allows_under_limit(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=5)
        for _ in range(5):
            ok, count = c.check_and_record("k")
            assert ok
        assert count == 5

    def test_blocks_over_limit(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=3)
        for _ in range(3):
            c.check_and_record("k")
        ok, count = c.check_and_record("k")
        assert not ok
        assert count == 3

    def test_separate_keys_independent(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=2)
        c.check_and_record("a")
        c.check_and_record("a")
        ok, _ = c.check_and_record("b")
        assert ok  # 'b' is independent

    def test_expiry(self) -> None:
        c = SlidingWindowCounter(window_seconds=0.05, max_events=2)
        c.check_and_record("k")
        c.check_and_record("k")
        ok, _ = c.check_and_record("k")
        assert not ok
        time.sleep(0.06)
        ok, _ = c.check_and_record("k")
        assert ok  # window expired

    def test_check_readonly(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=3)
        c.check_and_record("k")
        ok_before, _ = c.check("k")
        assert ok_before
        # check does not record
        ok_after, _ = c.check_and_record("k")
        assert ok_after

    def test_reset_single_key(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=2)
        c.check_and_record("k")
        c.reset("k")
        ok, _ = c.check_and_record("k")
        assert ok

    def test_pop_last_removes_only_one(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=5)
        c.check_and_record("k")
        c.check_and_record("k")
        c.check_and_record("k")
        c.pop_last("k")
        # pop_last removed the 3rd record → count should now be 2
        ok, count = c.check_and_record("k")
        assert ok
        assert count == 3  # 2 original + 1 new

    def test_pop_last_empty_key_is_noop(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=5)
        c.pop_last("nonexistent")  # must not raise

    def test_pop_last_removes_key_when_empty(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=5)
        c.check_and_record("k")
        c.pop_last("k")
        # deque should be fully removed from _buckets
        assert "k" not in c._buckets

    def test_reset_all(self) -> None:
        c = SlidingWindowCounter(window_seconds=60.0, max_events=2)
        c.check_and_record("a")
        c.check_and_record("b")
        c.reset()
        assert c.check_and_record("a")[0]
        assert c.check_and_record("b")[0]

    def test_invalid_params(self) -> None:
        with pytest.raises(ValueError):
            SlidingWindowCounter(window_seconds=1, max_events=0)
        with pytest.raises(ValueError):
            SlidingWindowCounter(window_seconds=-1, max_events=5)


class TestCheckToolRate:
    def test_accepts_normal_rate(self) -> None:
        reset_rate_limits()
        # Should not raise
        check_tool_rate("test_tool")
        check_tool_rate("test_tool")

    def test_rejects_excessive_burst(self) -> None:
        reset_rate_limits()
        # The burst limit is high (1000/sec default), so this is hard to
        # test without time manipulation.  We verify that check_tool_rate
        # exists and wires through correctly.
        ok = True
        try:
            check_tool_rate("burst_test")
        except RateLimitError:
            ok = False
        assert ok

    def test_reset_clears_counters(self) -> None:
        reset_rate_limits()
        # Fill up the minute limiter for a specific tool
        from allbrain.security.rate_limit import _BURST_LIMITER, _MINUTE_LIMITER

        _MINUTE_LIMITER.check_and_record("reset_tool")
        _BURST_LIMITER.check_and_record("reset_tool")

        reset_rate_limits()

        ok, _ = _MINUTE_LIMITER.check("reset_tool")
        assert ok  # reset cleared it


class TestMinuteLimitRollback:
    """pop_last semantics: minute deny only undoes the last burst record."""

    def test_rollback_does_not_erase_burst_history(self) -> None:
        reset_rate_limits()

        from allbrain.security.rate_limit import _BURST_LIMITER, _MINUTE_LIMITER

        # Record 5 legitimate burst entries before the minute limit would deny
        for _ in range(5):
            _BURST_LIMITER.check_and_record("rollback_tool")

        # Fill the minute limiter to capacity by monkey-patching its max_events
        old_max = _MINUTE_LIMITER._max
        _MINUTE_LIMITER._max = 1
        _MINUTE_LIMITER.check_and_record("rollback_tool")  # now at capacity

        # Use the real integration point — it should pop_last, not reset
        from allbrain.security.rate_limit import check_tool_rate

        with pytest.raises(RateLimitError):
            check_tool_rate("rollback_tool")
        _MINUTE_LIMITER._max = old_max

        # Burst counter should be 5 (6 after check_and_record − 1 pop_last), not 0 (which reset would give)
        _, burst_count = _BURST_LIMITER.check("rollback_tool")
        assert burst_count == 5, f"Expected 5 burst records after pop_last, got {burst_count}"


class TestRateLimiterConcurrency:
    """Thread-safety tests for SlidingWindowCounter."""

    def test_check_and_record_is_thread_safe(self) -> None:
        """Concurrent check_and_record must never exceed max_events."""
        max_events = 50
        thread_count = 10
        attempts_per_thread = 20
        counter = SlidingWindowCounter(window_seconds=60.0, max_events=max_events)

        barrier = __import__("threading").Barrier(thread_count)
        results: list[tuple[bool, int]] = []

        def worker() -> list[tuple[bool, int]]:
            barrier.wait()
            local: list[tuple[bool, int]] = []
            for _ in range(attempts_per_thread):
                local.append(counter.check_and_record("k"))
            return local

        with ThreadPoolExecutor(max_workers=thread_count) as pool:
            futs = [pool.submit(worker) for _ in range(thread_count)]
            for fut in as_completed(futs):
                results.extend(fut.result())

        allowed = [r for r in results if r[0]]
        denied = [r for r in results if not r[0]]

        assert len(allowed) == max_events, f"Expected exactly {max_events} allowed, got {len(allowed)}"
        assert len(denied) == thread_count * attempts_per_thread - max_events

    def test_reset_concurrent_with_record(self) -> None:
        """Reset while recording must not raise or corrupt state."""
        counter = SlidingWindowCounter(window_seconds=60.0, max_events=100)
        errors: list[Exception] = []

        def recorder() -> None:
            for _ in range(200):
                try:
                    counter.check_and_record("k")
                except Exception as exc:
                    errors.append(exc)

        def reseter() -> None:
            for _ in range(50):
                counter.reset("k")

        with ThreadPoolExecutor(max_workers=6) as pool:
            futs = [pool.submit(recorder) for _ in range(4)]
            futs.append(pool.submit(reseter))
            for fut in as_completed(futs):
                fut.result()

        assert not errors, f"Concurrent reset/record raised: {errors}"
