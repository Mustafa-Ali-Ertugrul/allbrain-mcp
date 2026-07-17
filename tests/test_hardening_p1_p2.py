"""Hardening: snapshot lease helpers, registry cache, session ensure outside lock."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

from allbrain.orchestrator.capabilities import CapabilityRegistry
from allbrain.orchestrator.scheduler import DeterministicScheduler
from allbrain.server.tools._shared import (
    _advisory_lock_key,
    _force_remove_lease,
    _try_create_lease,
)
from tests._helpers import make_context


def test_advisory_lock_key_stable_and_positive(tmp_path: Path) -> None:
    a = _advisory_lock_key(tmp_path)
    b = _advisory_lock_key(tmp_path)
    assert a == b
    assert a >= 0
    assert a <= 0x7FFFFFFFFFFFFFFF


def test_file_lease_acquire_and_release(tmp_path: Path) -> None:
    lease = tmp_path / "lease.lock"
    assert _try_create_lease(lease) is True
    assert lease.is_dir()
    assert _try_create_lease(lease) is False  # held
    assert _force_remove_lease(lease) is True
    assert _try_create_lease(lease) is True
    _force_remove_lease(lease)


def test_capability_registry_from_env_cached(monkeypatch) -> None:
    CapabilityRegistry.reset_default_cache()
    monkeypatch.delenv("ALLBRAIN_CAPABILITIES_PATH", raising=False)
    a = CapabilityRegistry.from_env()
    b = CapabilityRegistry.from_env()
    assert a is b
    s1 = DeterministicScheduler()
    s2 = DeterministicScheduler()
    assert s1.registry is s2.registry
    CapabilityRegistry.reset_default_cache()


def test_ensure_active_session_create_outside_lock(tmp_path: Path) -> None:
    context = make_context(tmp_path, active=False)
    assert context.active_session is None
    hold = threading.Event()
    entered = threading.Event()
    created: list[object] = []

    original = context._repository.create_session

    def slow_create(*args, **kwargs):
        entered.set()
        hold.wait(timeout=2)
        session = original(*args, **kwargs)
        created.append(session)
        return session

    context._repository.create_session = slow_create  # type: ignore[method-assign]
    results: list[object] = []

    def worker() -> None:
        results.append(context.ensure_active_session())

    t1 = threading.Thread(target=worker)
    t1.start()
    assert entered.wait(timeout=2)
    # While create is in flight, lock should not block active_session read.
    with context._session_lock:
        assert context.active_session is None
    hold.set()
    t1.join(timeout=5)
    assert len(results) == 1
    assert context.active_session is not None
