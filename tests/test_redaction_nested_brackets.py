"""Tests for Pydantic ValidationError input_value redaction (BUG-3 fix).

The old regex ``[^,\\]]`` stopped at the first comma inside bracketed
expressions like ``input_value='sk-abc...', input_type=str``, leaking
the remainder. The fixed regex uses a lookahead that correctly handles
commas inside the input_value field.
"""

from __future__ import annotations

import re

_PYDANTIC_INPUT_RE = re.compile(r",?\s*input_value=(?:(?!,\s*\w+=|\])[^]])*")


def test_strips_simple_input_value() -> None:
    msg = "Input should be a valid string [type=string_type, input_value='hello', input_type=str]"
    result = _PYDANTIC_INPUT_RE.sub("", msg)
    assert "hello" not in result
    assert "type=string_type" in result
    assert "input_type=str" in result


def test_strips_input_value_with_commas_in_brackets() -> None:
    """BUG-3: old regex leaked text after commas inside bracket expressions."""
    msg = "Input should be a valid string [type=string_type, input_value='sk-abc123def456...', input_type=str]"
    result = _PYDANTIC_INPUT_RE.sub("", msg)
    assert "sk-abc123def456" not in result
    assert "type=string_type" in result
    assert "input_type=str" in result


def test_strips_input_value_with_nested_brackets() -> None:
    """input_value containing bracket chars should be fully removed."""
    msg = "Error [type=value_error, input_value='[1, 2, 3]', input_type=list]"
    result = _PYDANTIC_INPUT_RE.sub("", msg)
    assert "[1, 2, 3]" not in result
    assert "type=value_error" in result
    assert "input_type=list" in result


def test_strips_long_input_value() -> None:
    """Long input_value (e.g. full API key) must be fully stripped."""
    long_key = "sk-" + "x" * 100
    msg = f"Error [type=string_type, input_value='{long_key}', input_type=str]"
    result = _PYDANTIC_INPUT_RE.sub("", msg)
    assert long_key not in result
    assert "type=string_type" in result


def test_preserves_non_input_value_fields() -> None:
    """Fields other than input_value must be preserved."""
    msg = "Error [type=string_type, loc=('body', 'name'), input_value='bad', input_type=str]"
    result = _PYDANTIC_INPUT_RE.sub("", msg)
    assert "type=string_type" in result
    assert "loc=" in result
    assert "input_type=str" in result


def test_no_input_value_unchanged() -> None:
    """Messages without input_value are unchanged."""
    msg = "Error [type=string_type, input_type=str]"
    result = _PYDANTIC_INPUT_RE.sub("", msg)
    assert result == msg


def test_leading_comma_stripped() -> None:
    """When input_value is the first field, the leading comma must also be removed."""
    msg = "Error [input_value='secret', input_type=str]"
    result = _PYDANTIC_INPUT_RE.sub("", msg)
    assert "secret" not in result
    assert "input_type=str" in result


def test_sanitize_valerr_msg_strips_and_redacts() -> None:
    """Integration: sanitize_valerr_msg strips input_value then redacts secrets."""
    from allbrain.security.redaction import sanitize_valerr_msg

    msg = "Error [type=string_type, input_value='sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMN', input_type=str]"
    result = sanitize_valerr_msg(msg)
    assert "sk-" not in result
    assert "type=string_type" in result
    assert "input_type=str" in result
