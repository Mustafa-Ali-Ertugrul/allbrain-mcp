from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class BrainContext:
    repository: Any  # BrainRepository - lazy import to avoid cycle
    project_path: str
    active_session: Any | None = None
    auto_snapshot_threshold: int = 100
    snapshot_check_interval: int = 100

    def __init__(self: BrainContext, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._event_count: int = 0
        self._count_lock: threading.Lock = threading.Lock()

    @property
    def active_session_id(self) -> int | None:
        if self.active_session is None:
            return None
        return self.active_session.id

    def increment_and_check_event_count(self) -> bool:
        with self._count_lock:
            self._event_count += 1
            if self._event_count >= self.snapshot_check_interval:
                self._event_count = 0
                return True
            return False
