from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from uuid6 import uuid7

from allbrain.server.constants import DEFAULT_AUTO_SNAPSHOT_THRESHOLD


@dataclass
class BrainContext:
    repository: Any  # BrainRepository - lazy import to avoid cycle
    project_path: str
    active_session: Any | None = None
    agent_name: str = "unknown"
    server_instance_id: str = ""
    client_name: str | None = None
    client_version: str | None = None
    central_audit_enabled: bool = False
    auto_snapshot_threshold: int = DEFAULT_AUTO_SNAPSHOT_THRESHOLD
    snapshot_check_interval: int = DEFAULT_AUTO_SNAPSHOT_THRESHOLD

    def __init__(self: BrainContext, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        if not getattr(self, "server_instance_id", ""):
            self.server_instance_id = str(uuid7())
        if getattr(self, "active_session", None) is not None and "agent_name" not in kwargs:
            self.agent_name = self.active_session.agent_name
        self._event_count: int = 0
        self._count_lock: threading.Lock = threading.Lock()
        self._session_lock: threading.RLock = threading.RLock()
        self.git_baseline: dict[str, Any] | None = None

    @property
    def active_session_id(self) -> int | None:
        if self.active_session is None:
            return None
        return self.active_session.id

    def set_client_info(self, name: str | None, version: str | None) -> None:
        if name:
            self.client_name = name
        if version:
            self.client_version = version

    def ensure_active_session(self) -> Any:
        with self._session_lock:
            if self.active_session is None:
                self.active_session = self.repository.create_session(
                    project_path=self.project_path,
                    agent_name=self.agent_name,
                    server_instance_id=self.server_instance_id,
                    client_name=self.client_name,
                    client_version=self.client_version,
                )
            return self.active_session

    def increment_and_check_event_count(self) -> bool:
        with self._count_lock:
            self._event_count += 1
            if self._event_count >= self.snapshot_check_interval:
                self._event_count = 0
                return True
            return False
