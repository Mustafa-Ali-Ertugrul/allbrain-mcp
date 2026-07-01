from __future__ import annotations

import threading
from typing import Any

from uuid6 import uuid7

from allbrain.server.constants import DEFAULT_AUTO_SNAPSHOT_THRESHOLD


class BrainContext:
    """Thread-safe brain execution context.

    Every mutable attribute is guarded by ``_session_lock`` (RLock).
    ``repository`` is read-only.  Immutable-after-init attributes
    (``project_path``, ``server_instance_id``, ``central_audit_enabled``,
    ``auto_snapshot_threshold``, ``snapshot_check_interval``) are plain
    public fields – they are never mutated outside ``__init__``.
    """

    def __init__(self: BrainContext, **kwargs: Any) -> None:
        # ── thread synchronisation (must be created first) ──
        self.__dict__["_session_lock"] = threading.RLock()
        self.__dict__["_count_lock"] = threading.Lock()

        # ── backing fields for property-backed attributes ──
        repo = kwargs.get("repository")
        self.__dict__["_repository"] = repo
        self.__dict__["_active_session"] = kwargs.get("active_session")

        # Immutable-after-init attributes (plain, never mutated outside __init__).
        self.project_path: str = kwargs.get("project_path", "")
        self.server_instance_id: str = kwargs.get("server_instance_id", "") or str(uuid7())
        self.central_audit_enabled: bool = kwargs.get("central_audit_enabled", False)
        self.auto_snapshot_threshold: int = kwargs.get("auto_snapshot_threshold", DEFAULT_AUTO_SNAPSHOT_THRESHOLD)
        self.snapshot_check_interval: int = kwargs.get("snapshot_check_interval", DEFAULT_AUTO_SNAPSHOT_THRESHOLD)

        # ── mutable attributes (backed by ``__dict__``, guarded by _session_lock) ──
        agent_name: str = kwargs.get("agent_name", "unknown")
        self.__dict__["_agent_name"] = agent_name
        self.__dict__["_client_name"] = kwargs.get("client_name")
        self.__dict__["_client_version"] = kwargs.get("client_version")
        self.__dict__["_git_baseline"]: dict[str, Any] | None = None
        self.__dict__["_event_count"]: int = 0

        # Infer agent_name from an existing session when not explicitly provided.
        if self.__dict__["_active_session"] is not None and "agent_name" not in kwargs:
            self._agent_name = self.__dict__["_active_session"].agent_name

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
        """Session id fetched under a single lock acquisition."""
        with self._session_lock:
            session = self._active_session
            if session is None:
                return None
            return session.id

    @property
    def agent_name(self) -> str:
        """Agent name (thread-safe)."""
        with self._session_lock:
            return self._agent_name

    @agent_name.setter
    def agent_name(self, value: str) -> None:
        with self._session_lock:
            self._agent_name = value

    @property
    def client_name(self) -> str | None:
        """Client name (thread-safe)."""
        with self._session_lock:
            return self._client_name

    @client_name.setter
    def client_name(self, value: str | None) -> None:
        with self._session_lock:
            self._client_name = value

    @property
    def client_version(self) -> str | None:
        """Client version (thread-safe)."""
        with self._session_lock:
            return self._client_version

    @client_version.setter
    def client_version(self, value: str | None) -> None:
        with self._session_lock:
            self._client_version = value

    @property
    def git_baseline(self) -> dict[str, Any] | None:
        """Git fingerprint baseline (thread-safe)."""
        with self._session_lock:
            return self._git_baseline

    @git_baseline.setter
    def git_baseline(self, value: dict[str, Any] | None) -> None:
        with self._session_lock:
            self._git_baseline = value

    # ── public methods ──

    def set_client_info(self, name: str | None, version: str | None) -> None:
        with self._session_lock:
            if name:
                self._client_name = name
            if version:
                self._client_version = version

    def ensure_active_session(self) -> Any:
        with self._session_lock:
            if self._active_session is None:
                self._active_session = self._repository.create_session(
                    project_path=self.project_path,
                    agent_name=self._agent_name,
                    server_instance_id=self.server_instance_id,
                    client_name=self._client_name,
                    client_version=self._client_version,
                )
            return self._active_session

    def increment_and_check_event_count(self) -> bool:
        with self._count_lock:
            self._event_count += 1
            if self._event_count >= self.snapshot_check_interval:
                self._event_count = 0
                return True
            return False
