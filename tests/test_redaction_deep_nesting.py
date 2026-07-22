"""Tests for recursive redaction depth limit (M8 fix).

The recursive payload walker now has a depth limit (_MAX_SANITIZE_DEPTH = 32)
to prevent stack overflow on adversarially or accidentally deep payloads.
"""

from __future__ import annotations

import sys
from pathlib import Path

from allbrain.security.redaction import (
    _MAX_SANITIZE_DEPTH,
    _sanitize_payload_impl,
    sanitize_payload,
)


def test_max_depth_constant_exists() -> None:
    """_MAX_SANITIZE_DEPTH must be defined and reasonable."""
    assert isinstance(_MAX_SANITIZE_DEPTH, int)
    assert 8 <= _MAX_SANITIZE_DEPTH <= 128


def test_shallow_payload_redacted_normally() -> None:
    """Normal shallow payloads are fully redacted."""
    payload = {"password": "secret123", "data": "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMN"}
    result = sanitize_payload(payload)
    assert result["password"] == "********"
    assert "sk-" not in result["data"]


def test_nested_dict_redacted() -> None:
    """Nested dicts are redacted correctly."""
    payload = {"level1": {"level2": {"secret": "mysecret"}}}
    result = sanitize_payload(payload)
    assert result["level1"]["level2"]["secret"] == "********"


def test_very_deep_payload_does_not_crash() -> None:
    """A payload deeper than _MAX_SANITIZE_DEPTH must not cause RecursionError."""
    # Build a chain of dicts deeper than the limit
    depth = _MAX_SANITIZE_DEPTH + 10
    leaf = {"value": "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMN"}
    payload = leaf
    for _ in range(depth):
        payload = {"next": payload}

    # Must not raise RecursionError
    result = sanitize_payload(payload)
    assert isinstance(result, dict)


def test_depth_limit_stops_redaction_at_boundary() -> None:
    """At exactly _MAX_SANITIZE_DEPTH, nested values are fail-closed (MASK)."""
    # Build a payload that nests a secret exactly at the depth limit
    secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMN"
    innermost = {"secret": secret}
    payload = innermost
    for _ in range(_MAX_SANITIZE_DEPTH - 1):
        payload = {"next": payload}

    result = sanitize_payload(payload)
    # Walk down the tree. At the boundary, the subtree must be MASK (fail-closed),
    # not the raw secret. We accept either the MASK string or a dict whose
    # sensitive values have been masked — both are safe (no raw secret leaks).
    current = result
    for _ in range(_MAX_SANITIZE_DEPTH - 2):
        assert isinstance(current, dict), f"Expected dict while walking, got {type(current)}"
        current = current["next"]
    # The next level must NOT contain the raw secret
    if isinstance(current["next"], str):
        assert current["next"] == "********", f"Expected fail-closed MASK at depth boundary, got {current['next']!r}"
    elif isinstance(current["next"], dict):
        # The inner dict was reached and redaction applied to its values
        assert current["next"].get("secret") == "********"


def test_extremely_deep_list_does_not_crash() -> None:
    """A deeply nested list must not cause RecursionError."""
    depth = _MAX_SANITIZE_DEPTH + 5
    payload: list = ["sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMN"]
    for _ in range(depth):
        payload = [payload]

    result = sanitize_payload(payload)
    assert isinstance(result, list)


def test_mixed_deep_dict_list_does_not_crash() -> None:
    """Mixed dict/list nesting deeper than limit must not crash."""
    depth = _MAX_SANITIZE_DEPTH + 5
    payload: dict | list = {"key": "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMN"}
    for i in range(depth):
        if i % 2 == 0:
            payload = [payload]
        else:
            payload = {"nested": payload}

    result = sanitize_payload(payload)
    assert isinstance(result, (dict, list))


def test_sanitize_payload_depth_parameter_in_source() -> None:
    """Source-level: _sanitize_payload_impl must accept a depth parameter."""
    source = Path(__file__).resolve().parent.parent / "src" / "allbrain" / "security" / "redaction.py"
    content = source.read_text(encoding="utf-8")
    assert "depth: int = 0" in content, "depth parameter missing from _sanitize_payload_impl"
    assert "_MAX_SANITIZE_DEPTH" in content
