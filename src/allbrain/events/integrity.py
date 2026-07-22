"""Lightweight tamper-evidence hash-chain for event payloads.

Hash = sha256(prev_event_hash + canonical_current_payload_json).
The first event in a project chain uses prev_hash = ``GENESIS``.

This is intentionally *not* a cryptographic signature scheme — it only
detects accidental or simple offline tampering of stored payloads.
Full signed/tamper-proof integrity is deferred to v1.2.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS = "genesis"
INTEGRITY_HASH_KEY = "integrity_hash"


def _canonical_body(payload: dict[str, Any]) -> str:
    """Serialize payload without the integrity field for stable hashing."""
    body = {k: v for k, v in payload.items() if k != INTEGRITY_HASH_KEY}
    return json.dumps(body, ensure_ascii=True, sort_keys=True, default=str, separators=(",", ":"))


def compute_integrity_hash(prev_hash: str | None, payload: dict[str, Any]) -> str:
    """Compute sha256(prev_hash + canonical_payload_json).

    Missing / empty *prev_hash* is treated as ``GENESIS`` for backward
    compatibility with pre-hash-chain event logs.
    """
    base = prev_hash if prev_hash else GENESIS
    material = f"{base}{_canonical_body(payload)}".encode()
    return hashlib.sha256(material).hexdigest()


def attach_integrity_hash(payload: dict[str, Any], prev_hash: str | None) -> dict[str, Any]:
    """Return a shallow copy of *payload* with ``integrity_hash`` set."""
    out = dict(payload)
    out.pop(INTEGRITY_HASH_KEY, None)
    out[INTEGRITY_HASH_KEY] = compute_integrity_hash(prev_hash, out)
    return out


def extract_integrity_hash(payload: dict[str, Any] | None) -> str | None:
    """Return stored integrity hash, or None when absent (legacy events)."""
    if not isinstance(payload, dict):
        return None
    value = payload.get(INTEGRITY_HASH_KEY)
    return value if isinstance(value, str) and value else None


def verify_hash_chain(events: list[dict[str, Any]]) -> list[int]:
    """Verify a sequence of payload dicts ordered oldest→newest.

    Returns a list of indices whose stored hash does not match recomputation.
    Legacy events without ``integrity_hash`` are treated as chain breaks only
    when a *later* event claims a non-genesis predecessor incorrectly — missing
    hashes themselves are tolerated (backward compatible).
    """
    mismatches: list[int] = []
    prev: str = GENESIS
    for idx, payload in enumerate(events):
        if not isinstance(payload, dict):
            mismatches.append(idx)
            prev = GENESIS
            continue
        stored = extract_integrity_hash(payload)
        if stored is None:
            # Pre-chain event: do not fail, but reset chain base.
            prev = GENESIS
            continue
        expected = compute_integrity_hash(prev, payload)
        if stored != expected:
            mismatches.append(idx)
        prev = stored
    return mismatches
