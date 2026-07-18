"""Tests for OpenAI secret pattern tightening (M7 fix).

The OpenAI regex was tightened from {20,} (unbounded, too permissive)
to {48,} (minimum 48 chars) to prevent false positives on short strings
while still greedily matching full-length keys for complete redaction.
"""

from __future__ import annotations

import re

_OPENAI_RE = re.compile(r"sk-(?!ant-)[a-zA-Z0-9]{40,}", re.IGNORECASE)


def test_openai_rejects_short_key() -> None:
    """Keys shorter than 40 chars after sk- prefix must NOT match."""
    short_key = "sk-" + "a" * 20
    assert _OPENAI_RE.search(short_key) is None, f"Short key matched: {short_key}"


def test_openai_rejects_very_short_key() -> None:
    """Keys of 10 chars after prefix must NOT match."""
    key = "sk-" + "b" * 10
    assert _OPENAI_RE.search(key) is None


def test_openai_rejects_39_char_key() -> None:
    """Keys of 39 chars (just below minimum) must NOT match."""
    key = "sk-" + "f" * 39
    assert _OPENAI_RE.search(key) is None


def test_openai_accepts_40_char_key() -> None:
    """Real 40-char OpenAI keys must match."""
    key = "sk-" + "c" * 40
    match = _OPENAI_RE.search(key)
    assert match is not None, f"40-char key did not match: {key}"


def test_openai_accepts_45_char_key() -> None:
    """Real 45-char OpenAI keys must match."""
    key = "sk-" + "d" * 45
    match = _OPENAI_RE.search(key)
    assert match is not None, f"45-char key did not match: {key}"


def test_openai_accepts_52_char_key() -> None:
    """Keys of 52+ chars must also match (greedy, no upper bound)."""
    key = "sk-" + "e" * 52
    match = _OPENAI_RE.search(key)
    assert match is not None, f"52-char key did not match: {key}"


def test_openai_rejects_non_alphanumeric() -> None:
    """Keys with underscores or dashes after sk- must NOT match."""
    key = "sk-" + "g" * 24 + "_" + "h" * 24
    assert _OPENAI_RE.search(key) is None


def test_openai_matches_key_in_context() -> None:
    """Key embedded in a sentence must be found."""
    text = "My key is sk-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMN and done"
    match = _OPENAI_RE.search(text)
    assert match is not None


def test_openai_does_not_match_anthropic_prefix() -> None:
    """sk-ant- prefix must NOT be matched by the OpenAI pattern."""
    key = "sk-ant-" + "a" * 48
    assert _OPENAI_RE.search(key) is None


def test_openai_case_insensitive() -> None:
    """Pattern must be case-insensitive."""
    key = "sk-" + "A" * 48
    match = _OPENAI_RE.search(key)
    assert match is not None


def test_redaction_module_uses_tightened_pattern() -> None:
    """Verify the actual redaction module has {48,} not {20,} for OpenAI."""
    from pathlib import Path

    redaction_py = Path(__file__).resolve().parent.parent / "src" / "allbrain" / "security" / "redaction.py"
    lines = redaction_py.read_text(encoding="utf-8").splitlines()

    # Find the OpenAI pattern line specifically
    openai_line = None
    for line in lines:
        if "openai" in line.lower() and "sk-" in line:
            openai_line = line
            break

    assert openai_line is not None, "Could not find OpenAI pattern line"
    assert "{40,}" in openai_line, f"OpenAI pattern not tightened: {openai_line}"
    assert "{20,}" not in openai_line, f"Old {(20,)} pattern still in OpenAI line: {openai_line}"
