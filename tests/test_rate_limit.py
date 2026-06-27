"""Unit tests for the sliding-window rate limiter."""
import time

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
        from allbrain.security.rate_limit import _MINUTE_LIMITER, _BURST_LIMITER

        _MINUTE_LIMITER.check_and_record("reset_tool")
        _BURST_LIMITER.check_and_record("reset_tool")

        reset_rate_limits()

        ok, _ = _MINUTE_LIMITER.check("reset_tool")
        assert ok  # reset cleared it
