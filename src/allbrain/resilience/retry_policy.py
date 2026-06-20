from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    delay_seconds: float
    reason: str


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 5.0

    def decide(self, *, attempt: int, error_type: str | None = None) -> RetryDecision:
        if attempt >= self.max_attempts:
            return RetryDecision(False, 0.0, "max_attempts_exceeded")
        delay = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** max(attempt - 1, 0)))
        return RetryDecision(True, delay, error_type or "retryable")
