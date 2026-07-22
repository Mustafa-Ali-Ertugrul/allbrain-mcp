"""Tests for v1.1 fail-closed sanitization remediation (§B1).

The recursive redaction walker previously returned the raw subtree
once depth >= _MAX_SANITIZE_DEPTH (fail-open). This suite verifies the
new fail-closed behavior: the subtree is replaced with MASK and a
``depth_limit`` counter is recorded in the redaction summary.

Also covers the env-configurable depth (ALLBRAIN_SANITIZE_MAX_DEPTH) and
the save_event payload size cap (ALLBRAIN_MAX_PAYLOAD_BYTES).
"""

from __future__ import annotations

import logging

import pytest

from allbrain.security.redaction import (
    _get_max_sanitize_depth,
    _sanitize_payload_impl,
    sanitize_payload,
)

# ---------------------------------------------------------------------------
# Fail-closed depth limit
# ---------------------------------------------------------------------------


def test_sanitize_depth_limit_masks_value() -> None:
    """A secret nested deeper than _MAX_SANITIZE_DEPTH must be masked (fail-closed)."""
    secret = "sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMN"
    payload: dict = {"secret": secret}
    # Wrap the secret so it lands beyond the depth limit
    for _ in range(40):
        payload = {"next": payload}

    result = sanitize_payload(payload)
    # Walk down to the masked level
    current = result
    for _ in range(31):
        current = current["next"]
    # Fail-closed: the remainder of the tree must be MASK
    assert current["next"] == "********"


def test_sanitize_depth_limit_increments_counter() -> None:
    """The found_types dict must record depth_limit hits for observability."""
    found_types: dict[str, int] = {}
    payload: dict = {"deep": "value"}
    for _ in range(40):
        payload = {"next": payload}

    _sanitize_payload_impl(payload, found_types)
    assert found_types.get("depth_limit", 0) > 0


def test_sanitize_depth_limit_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Reaching the depth limit must emit a structured warning for observability."""
    payload: dict = {"deep": "value"}
    for _ in range(40):
        payload = {"next": payload}

    with caplog.at_level(logging.WARNING, logger="allbrain.security.redaction"):
        sanitize_payload(payload)
    assert any(
        "sanitize_depth_limit_reached" in r.message or "depth_limit" in str(r.args).lower() for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Env-configurable depth (ALLBRAIN_SANITIZE_MAX_DEPTH)
# ---------------------------------------------------------------------------


def test_max_sanitize_depth_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without env var, default depth is 32."""
    monkeypatch.delenv("ALLBRAIN_SANITIZE_MAX_DEPTH", raising=False)
    assert _get_max_sanitize_depth() == 32


def test_max_sanitize_depth_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """ALLBRAIN_SANITIZE_MAX_DEPTH overrides the default."""
    monkeypatch.setenv("ALLBRAIN_SANITIZE_MAX_DEPTH", "16")
    assert _get_max_sanitize_depth() == 16


def test_max_sanitize_depth_env_clamped_low(monkeypatch: pytest.MonkeyPatch) -> None:
    """Values below 1 are clamped to 1."""
    monkeypatch.setenv("ALLBRAIN_SANITIZE_MAX_DEPTH", "0")
    assert _get_max_sanitize_depth() == 1


def test_max_sanitize_depth_env_clamped_high(monkeypatch: pytest.MonkeyPatch) -> None:
    """Values above 256 are clamped to 256."""
    monkeypatch.setenv("ALLBRAIN_SANITIZE_MAX_DEPTH", "99999")
    assert _get_max_sanitize_depth() == 256


def test_max_sanitize_depth_env_invalid_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-integer env values fall back to the default."""
    monkeypatch.setenv("ALLBRAIN_SANITIZE_MAX_DEPTH", "not-a-number")
    assert _get_max_sanitize_depth() == 32


# ---------------------------------------------------------------------------
# save_event payload size cap (ALLBRAIN_MAX_PAYLOAD_BYTES)
# ---------------------------------------------------------------------------


def test_payload_size_cap_rejects_oversized(monkeypatch: pytest.MonkeyPatch) -> None:
    """A payload larger than ALLBRAIN_MAX_PAYLOAD_BYTES is rejected."""
    # Set a small cap for deterministic testing
    monkeypatch.setenv("ALLBRAIN_MAX_PAYLOAD_BYTES", "2048")
    from allbrain.models.schemas import SaveEventInput

    # Build a payload just over the 2KB cap
    big_value = "x" * 3000
    with pytest.raises(Exception, match="payload exceeds maximum size"):
        SaveEventInput.model_validate({"type": "test_event", "payload": {"data": big_value}})


def test_payload_size_cap_accepts_within_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A payload within the cap is accepted."""
    monkeypatch.setenv("ALLBRAIN_MAX_PAYLOAD_BYTES", "2048")
    from allbrain.models.schemas import SaveEventInput

    small_payload = {"data": "small value"}
    obj = SaveEventInput.model_validate({"type": "task_created", "payload": small_payload})
    assert obj.payload == small_payload


def test_payload_size_cap_env_default_used(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without env var, the default 250KB cap is used."""
    monkeypatch.delenv("ALLBRAIN_MAX_PAYLOAD_BYTES", raising=False)
    from allbrain.models.schemas import max_payload_bytes

    assert max_payload_bytes() == 250_000


def test_payload_size_cap_env_clamped_high(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env values above 1MB are clamped to 1MB."""
    monkeypatch.setenv("ALLBRAIN_MAX_PAYLOAD_BYTES", str(2 * 1024 * 1024))
    from allbrain.models.schemas import max_payload_bytes

    assert max_payload_bytes() == 1_048_576
