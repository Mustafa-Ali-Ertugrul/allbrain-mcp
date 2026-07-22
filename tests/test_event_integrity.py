"""Event integrity hash-chain (tamper-evidence)."""

from __future__ import annotations

import json
from pathlib import Path

from allbrain.events.integrity import (
    GENESIS,
    attach_integrity_hash,
    compute_integrity_hash,
    extract_integrity_hash,
    verify_hash_chain,
)
from allbrain.storage.database import create_engine_for_path, init_db
from allbrain.storage.repository import BrainRepository


def test_compute_integrity_hash_genesis_and_chain() -> None:
    p1 = {"msg": "a"}
    h1 = compute_integrity_hash(None, p1)
    assert h1 == compute_integrity_hash(GENESIS, p1)
    p2 = {"msg": "b"}
    h2 = compute_integrity_hash(h1, p2)
    assert h2 != h1
    assert len(h1) == 64


def test_legacy_payloads_without_hash_do_not_crash() -> None:
    chain = [
        {"msg": "legacy"},
        attach_integrity_hash({"msg": "fresh"}, None),
    ]
    # First is legacy (no hash) — tolerated; second starts from genesis.
    assert verify_hash_chain(chain) == []


def test_event_hash_chain_integrity(tmp_path: Path) -> None:
    """Tampering a stored payload breaks verification of subsequent hashes."""
    engine = create_engine_for_path(tmp_path / "chain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project = tmp_path / "proj"
    project.mkdir()

    session = repo.create_session(project, "tester")
    session_id = session.id or 0

    e1 = repo.append_event(
        project_path=project,
        session_id=session_id,
        type="file_modified",
        source="test",
        payload={"step": 1, "note": "alpha"},
    )
    e2 = repo.append_event(
        project_path=project,
        session_id=session_id,
        type="file_modified",
        source="test",
        payload={"step": 2, "note": "beta"},
    )
    e3 = repo.append_event(
        project_path=project,
        session_id=session_id,
        type="file_modified",
        source="test",
        payload={"step": 3, "note": "gamma"},
    )

    p1 = json.loads(e1.payload_json)
    p2 = json.loads(e2.payload_json)
    p3 = json.loads(e3.payload_json)
    assert extract_integrity_hash(p1)
    assert extract_integrity_hash(p2)
    assert extract_integrity_hash(p3)
    assert verify_hash_chain([p1, p2, p3]) == []

    # Tamper middle event body while keeping its old integrity_hash → mid fails.
    tampered = dict(p2)
    tampered["note"] = "EVIL"
    assert verify_hash_chain([p1, tampered, p3]) == [1]

    # Recompute mid hash for the evil body; e3 still fails (chained to old mid hash).
    fixed_mid = attach_integrity_hash({"step": 2, "note": "EVIL"}, extract_integrity_hash(p1))
    assert verify_hash_chain([p1, fixed_mid, p3]) == [2]


def test_append_event_attaches_integrity_hash(tmp_path: Path) -> None:
    engine = create_engine_for_path(tmp_path / "one.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project = tmp_path / "p"
    project.mkdir()

    session = repo.create_session(project, "t")
    event = repo.append_event(
        project_path=project,
        session_id=session.id or 0,
        type="tool_call",
        source="test",
        payload={"ok": True},
    )
    payload = json.loads(event.payload_json)
    assert extract_integrity_hash(payload) == compute_integrity_hash(GENESIS, {"ok": True})
    assert "_meta" in payload
    assert "integrity_hash" not in payload  # nested under _meta, not top-level
    # Public EventRead must not expose storage integrity metadata
    public = repo.list_events(project_path=project, limit=1)[0]
    assert "integrity_hash" not in public.payload
    assert "_meta" not in public.payload or "integrity_hash" not in public.payload.get("_meta", {})
