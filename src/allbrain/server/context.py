from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from uuid6 import uuid7

from allbrain.server.constants import (
    DEFAULT_AUTO_SNAPSHOT_THRESHOLD,
    DEFAULT_SNAPSHOT_CHECK_INTERVAL,
    DEFAULT_SNAPSHOT_MIN_INTERVAL_SECONDS,
)

if TYPE_CHECKING:
    from allbrain.models.entities import Session
    from allbrain.storage.repository import BrainRepository


class BrainContext:
    """Thread-safe brain execution context.

    Every mutable attribute is guarded by ``_session_lock`` (RLock).
    ``repository`` is read-only.  Immutable-after-init attributes
    (``project_path``, ``server_instance_id``, ``central_audit_enabled``,
    ``auto_snapshot_threshold``, ``snapshot_check_interval``,
    ``snapshot_min_interval_seconds``) are plain
    public fields – they are never mutated outside ``__init__``.
    """

    def __init__(
        self: BrainContext,
        *,
        repository: BrainRepository,
        project_path: str = "",
        active_session: Session | None = None,
        agent_name: str | None = None,
        server_instance_id: str = "",
        client_name: str | None = None,
        client_version: str | None = None,
        central_audit_enabled: bool = False,
        auto_snapshot_threshold: int = DEFAULT_AUTO_SNAPSHOT_THRESHOLD,
        snapshot_check_interval: int = DEFAULT_SNAPSHOT_CHECK_INTERVAL,
        snapshot_min_interval_seconds: float = DEFAULT_SNAPSHOT_MIN_INTERVAL_SECONDS,
    ) -> None:
        # ── thread synchronisation (must be created first) ──
        self.__dict__["_session_lock"] = threading.RLock()
        self.__dict__["_count_lock"] = threading.Lock()

        # ── backing fields for property-backed attributes ──
        self.__dict__["_repository"] = repository
        self.__dict__["_active_session"] = active_session

        # Immutable-after-init attributes (plain, never mutated outside __init__).
        self.project_path = project_path
        self.server_instance_id = server_instance_id or str(uuid7())
        self.central_audit_enabled = central_audit_enabled
        self.auto_snapshot_threshold = auto_snapshot_threshold
        self.snapshot_check_interval = snapshot_check_interval
        self.snapshot_min_interval_seconds = snapshot_min_interval_seconds

        # ── mutable attributes (backed by ``__dict__``, guarded by _session_lock) ──
        resolved_agent_name = agent_name or (active_session.agent_name if active_session is not None else "unknown")
        self.__dict__["_agent_name"] = resolved_agent_name
        self.__dict__["_client_name"] = client_name
        self.__dict__["_client_version"] = client_version
        self.__dict__["_git_baseline"]: dict[str, Any] | None = None
        self.__dict__["_event_count"]: int = 0

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
        """Return active session; create outside the lock to avoid holding it on DB I/O."""
        with self._session_lock:
            if self._active_session is not None:
                return self._active_session
            project_path = self.project_path
            agent_name = self._agent_name
            server_instance_id = self.server_instance_id
            client_name = self._client_name
            client_version = self._client_version
        # DB write outside lock (SQLite busy_timeout serializes writers).
        created = self._repository.create_session(
            project_path=project_path,
            agent_name=agent_name,
            server_instance_id=server_instance_id,
            client_name=client_name,
            client_version=client_version,
        )
        with self._session_lock:
            if self._active_session is None:
                self._active_session = created
            return self._active_session

    def increment_and_check_event_count(self) -> bool:
        with self._count_lock:
            self._event_count += 1
            if self._event_count >= self.snapshot_check_interval:
                self._event_count = 0
                return True
            return False
