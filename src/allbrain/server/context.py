from __future__ import annotations

import threading
from typing import Any

from uuid6 import uuid7

from allbrain.server.constants import DEFAULT_AUTO_SNAPSHOT_THRESHOLD


class BrainContext:
    """Thread-safe brain execution context.

    ``active_session`` is guarded by ``_session_lock`` (RLock) to prevent
    concurrent read/write races.  ``repository`` is a read-only property.
    """

    def __init__(self: BrainContext, **kwargs: Any) -> None:
        # ── thread synchronisation (must be created first) ──
        self.__dict__["_session_lock"] = threading.RLock()
        self.__dict__["_count_lock"] = threading.Lock()

        # ── backing fields for property-backed attributes ──
        repo = kwargs.get("repository")
        self.__dict__["_repository"] = repo
        self.__dict__["_active_session"] = kwargs.get("active_session")

        # ── plain attributes ──
        self.project_path: str = kwargs.get("project_path", "")
        self.agent_name: str = kwargs.get("agent_name", "unknown")
        self.server_instance_id: str = kwargs.get("server_instance_id", "") or str(uuid7())
        self.client_name: str | None = kwargs.get("client_name")
        self.client_version: str | None = kwargs.get("client_version")
        self.central_audit_enabled: bool = kwargs.get("central_audit_enabled", False)
        self.auto_snapshot_threshold: int = kwargs.get("auto_snapshot_threshold", DEFAULT_AUTO_SNAPSHOT_THRESHOLD)
        self.snapshot_check_interval: int = kwargs.get("snapshot_check_interval", DEFAULT_AUTO_SNAPSHOT_THRESHOLD)
        self._event_count: int = 0
        self.git_baseline: dict[str, Any] | None = None

        # Infer agent_name from an existing session when not explicitly provided.
        if self.__dict__["_active_session"] is not None and "agent_name" not in kwargs:
            self.agent_name = self.__dict__["_active_session"].agent_name

        # Catch any extra kwargs (forward-compat safety net).
        known = {
            "repository",
            "project_path",
            "active_session",
            "agent_name",
            "server_instance_id",
            "client_name",
            "client_version",
            "central_audit_enabled",
            "auto_snapshot_threshold",
            "snapshot_check_interval",
        }
        for k, v in kwargs.items():
            if k not in known:
                self.__dict__[k] = v

    # ── properties ──

    @property
    def repository(self) -> Any:
        """Read-only reference to BrainRepository."""
        return self._repository

    @property
    def active_session(self) -> Any | None:
        """Get the current active session (thread-safe, locked)."""
        with self._session_lock:
            return self._active_session

    @active_session.setter
    def active_session(self, value: Any | None) -> None:
        """Set the current active session (thread-safe, locked)."""
        with self._session_lock:
            self._active_session = value

    @property
    def active_session_id(self) -> int | None:
        session = self.active_session  # uses locked property
        if session is None:
            return None
        return session.id

    # ── public methods ──

    def set_client_info(self, name: str | None, version: str | None) -> None:
        if name:
            self.client_name = name
        if version:
            self.client_version = version

    def ensure_active_session(self) -> Any:
        with self._session_lock:
            if self._active_session is None:
                self._active_session = self._repository.create_session(
                    project_path=self.project_path,
                    agent_name=self.agent_name,
                    server_instance_id=self.server_instance_id,
                    client_name=self.client_name,
                    client_version=self.client_version,
                )
            return self._active_session

    def increment_and_check_event_count(self) -> bool:
        with self._count_lock:
            self._event_count += 1
            if self._event_count >= self.snapshot_check_interval:
                self._event_count = 0
                return True
            return False
