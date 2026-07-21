from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

Clock = Callable[[], datetime]


def utc_clock() -> datetime:
    return datetime.now(UTC)


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    recovery_seconds: int = 60
    clock: Clock = utc_clock
    state: str = "closed"
    consecutive_failures: int = 0
    opened_at: datetime | None = None

    def allow_request(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "half_open":
            return True
        if self.opened_at and self.clock() - self.opened_at >= timedelta(seconds=self.recovery_seconds):
            self.state = "half_open"
            return True
        return False

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.state = "closed"
        self.opened_at = None

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.state = "open"
            self.opened_at = self.clock()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "state": self.state,
            "consecutive_failures": self.consecutive_failures,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }
