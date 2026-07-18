"""Tests for EventType WEIGHTS_ADAPATED → WEIGHTS_ADAPTED typo fix (BUG-1).

The enum value was misspelled as ``weights_adapated`` (missing 't').
Fixed to ``weights_adapted`` with backward-compat aliases for existing
clients that may still send the old name.
"""

from __future__ import annotations

from allbrain.events.schemas import (
    _EVENT_TYPE_ALIASES,
    EventType,
    normalize_event_type_name,
)


def test_weights_adapted_canonical_value() -> None:
    """The canonical enum value must be 'weights_adapted'."""
    assert EventType.WEIGHTS_ADAPTED.value == "weights_adapted"


def test_weights_adapted_not_misspelled() -> None:
    """The old misspelled value 'weights_adapated' must not be the canonical value."""
    assert EventType.WEIGHTS_ADAPTED.value != "weights_adapated"


def test_weights_adapted_member_name() -> None:
    """The member name must be WEIGHTS_ADAPTED (not WEIGHTS_ADAPATED)."""
    assert hasattr(EventType, "WEIGHTS_ADAPTED")


def test_backward_compat_alias_snake_case() -> None:
    """The misspelled snake_case name must map to the canonical value."""
    alias = _EVENT_TYPE_ALIASES.get("weights_adapated")
    assert alias == "weights_adapted"


def test_backward_compat_alias_screaming() -> None:
    """The misspelled SCREAMING_SNAKE name must map to the canonical value."""
    alias = _EVENT_TYPE_ALIASES.get("WEIGHTS_ADAPATED")
    assert alias == "weights_adapted"


def test_normalize_accepts_canonical() -> None:
    """normalize_event_type_name accepts the corrected canonical name."""
    assert normalize_event_type_name("weights_adapted") == "weights_adapted"


def test_normalize_accepts_old_snake_case_alias() -> None:
    """normalize_event_type_name accepts the old misspelled name via alias."""
    assert normalize_event_type_name("weights_adapated") == "weights_adapted"


def test_normalize_accepts_old_screaming_alias() -> None:
    """normalize_event_type_name accepts the old misspelled SCREAMING name via alias."""
    assert normalize_event_type_name("WEIGHTS_ADAPATED") == "weights_adapted"
