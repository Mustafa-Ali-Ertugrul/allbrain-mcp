"""Lightweight tamper-evidence hash-chain for event payloads.

Hash = sha256(prev_event_hash + canonical_current_payload_json).
The first event in a project chain uses prev_hash = ``GENESIS``.

Integrity is stored under ``payload["_meta"]["integrity_hash"]`` so domain
payload schemas (``extra="forbid"``) and business equality checks remain
unchanged. Top-level ``integrity_hash`` is still accepted when reading legacy
rows written during early v1.1 development.

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
META_KEY = "_meta"


def _without_integrity_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of payload without integrity hash fields."""
    body = {k: v for k, v in payload.items() if k != INTEGRITY_HASH_KEY}
    meta = body.get(META_KEY)
    if isinstance(meta, dict):
        cleaned_meta = {k: v for k, v in meta.items() if k != INTEGRITY_HASH_KEY}
        if cleaned_meta:
            body[META_KEY] = cleaned_meta
        else:
            body.pop(META_KEY, None)
    return body


def _canonical_body(payload: dict[str, Any]) -> str:
    """Serialize payload without the integrity field for stable hashing."""
    return json.dumps(
        _without_integrity_fields(payload),
        ensure_ascii=True,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def compute_integrity_hash(prev_hash: str | None, payload: dict[str, Any]) -> str:
    """Compute sha256(prev_hash + canonical_payload_json).

    Missing / empty *prev_hash* is treated as ``GENESIS`` for backward
    compatibility with pre-hash-chain event logs.
    """
    base = prev_hash if prev_hash else GENESIS
    material = f"{base}{_canonical_body(payload)}".encode()
    return hashlib.sha256(material).hexdigest()


def attach_integrity_hash(payload: dict[str, Any], prev_hash: str | None) -> dict[str, Any]:
    """Return a copy of *payload* with integrity hash under ``_meta``."""
    out = _without_integrity_fields(dict(payload))
    digest = compute_integrity_hash(prev_hash, out)
    meta = dict(out[META_KEY]) if isinstance(out.get(META_KEY), dict) else {}
    meta[INTEGRITY_HASH_KEY] = digest
    out[META_KEY] = meta
    return out


def extract_integrity_hash(payload: dict[str, Any] | None) -> str | None:
    """Return stored integrity hash, or None when absent (legacy events)."""
    if not isinstance(payload, dict):
        return None
    # Preferred: nested under _meta
    meta = payload.get(META_KEY)
    if isinstance(meta, dict):
        nested = meta.get(INTEGRITY_HASH_KEY)
        if isinstance(nested, str) and nested:
            return nested
    # Legacy: top-level key from early v1.1 builds
    value = payload.get(INTEGRITY_HASH_KEY)
    return value if isinstance(value, str) and value else None


def strip_integrity_fields(payload: Any) -> Any:
    """Remove integrity fields from a public-facing payload copy."""
    if not isinstance(payload, dict):
        return payload
    return _without_integrity_fields(payload)


def verify_hash_chain(events: list[dict[str, Any]]) -> list[int]:
    """Verify a sequence of payload dicts ordered oldest→newest.

    Returns a list of indices whose stored hash does not match recomputation.
    Legacy events without ``integrity_hash`` are tolerated (backward compatible).
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
            prev = GENESIS
            continue
        expected = compute_integrity_hash(prev, payload)
        if stored != expected:
            mismatches.append(idx)
        prev = stored
    return mismatches
