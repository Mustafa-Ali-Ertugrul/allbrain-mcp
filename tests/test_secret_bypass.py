"""Test secret redaction edge cases — bypass attempts and pattern boundaries.

With re.IGNORECASE applied to all patterns (since the fix), uppercase
prefixes like SK- / GHP_ / AKIA are now caught.  Whitespace and newline
variants are (correctly) not caught — they are not real secrets.
"""

from pathlib import Path

import pytest

from allbrain.security.redaction import sanitize_payload


def test_lowercase_openai_key_masked() -> None:
    result = sanitize_payload({"key": "sk-" + "a" * 40})
    assert result["key"] == "********"


def test_uppercase_openai_key_masked() -> None:
    result = sanitize_payload({"key": "SK-" + "A" * 40})
    assert result["key"] == "********"


def test_mixed_case_openai_key_masked() -> None:
    result = sanitize_payload({"key": "Sk-" + "A" * 40})
    assert result["key"] == "********"


def test_uppercase_aws_key_masked() -> None:
    result = sanitize_payload({"key": "akia" + "a" * 16})
    assert result["key"] == "********"


def test_uppercase_github_pat_masked() -> None:
    result = sanitize_payload({"key": "GHP_" + "A" * 36})
    assert result["key"] == "********"


def test_space_in_prefix_not_masked() -> None:
    """Whitespace inside the prefix breaks the pattern — not a real secret."""
    result = sanitize_payload({"key": "sk -" + "a" * 40})
    assert result["key"] != "********"


def test_newline_breaks_pattern() -> None:
    """Newline inside the prefix breaks the pattern — not a real secret."""
    result = sanitize_payload({"key": "sk-\n" + "a" * 40})
    assert result["key"] != "********"


def test_secret_in_sentence_masked_only_part() -> None:
    value = "my key is sk-" + "a" * 40 + " please keep it safe"
    result = sanitize_payload({"key": value})
    assert "********" in result["key"]
    assert "my key is" in result["key"]
    assert "please keep it safe" in result["key"]


def test_multiple_overlapping_patterns(tmp_path: Path) -> None:
    value = "sk-" + "a" * 40 + " and ghp_" + "b" * 36
    result1 = sanitize_payload({"key": value})
    assert result1["key"].count("********") == 2


def test_short_secret_not_masked() -> None:
    """sk- with fewer than 20 chars is too short — not masked."""
    result = sanitize_payload({"key": "sk-" + "a" * 19})
    assert result["key"] == "sk-" + "a" * 19


def test_secret_in_nested_dict(tmp_path: Path) -> None:
    payload = {"a": {"b": ["sk-" + "a" * 40]}}
    result = sanitize_payload(payload)
    assert result["a"]["b"][0] == "********"


def test_secret_punctuation_boundary() -> None:
    value = "sk-" + "a" * 20 + "!"
    result = sanitize_payload({"key": value})
    assert "********" in result["key"]


def test_aws_key_too_short_not_masked() -> None:
    """AKIA + 15 chars (needs 16)."""
    result = sanitize_payload({"key": "AKIA" + "A" * 15})
    assert result["key"] != "********"


def test_slack_token_variants_masked() -> None:
    for prefix in ["xoxb-", "xoxa-", "xoxp-", "xoxr-", "xoxs-"]:
        result = sanitize_payload({"key": prefix + "abc123def456"})
        assert result["key"] == "********", f"failed for prefix {prefix}"


def test_no_false_positive_on_normal_text() -> None:
    result = sanitize_payload({"key": "skip-this-task-sk"})
    assert result["key"] == "skip-this-task-sk"


def test_anthropic_key_uppercase_masked() -> None:
    result = sanitize_payload({"key": "SK-ANT-" + "A" * 36})
    assert result["key"] == "********"


def test_github_refresh_uppercase_masked() -> None:
    result = sanitize_payload({"key": "GHR_" + "A" * 36})
    assert result["key"] == "********"


def test_jwt_token_masked() -> None:
    result = sanitize_payload({"key": "eyJh.eyJ0." + "a" * 43})
    assert result["key"] == "********"


def test_jwt_like_string_not_masked() -> None:
    """FP guard: two-part dot-separated string without signature segment."""
    result = sanitize_payload({"key": "eyJtest.invalid"})
    assert result["key"] == "eyJtest.invalid"


def test_ssh_openssh_private_key_masked() -> None:
    key = "-----BEGIN OPENSSH PRIVATE KEY-----\nABCD\n-----END OPENSSH PRIVATE KEY-----"
    result = sanitize_payload({"key": key})
    assert result["key"] == "********"


def test_ssh_rsa_private_key_masked() -> None:
    key = "-----BEGIN RSA PRIVATE KEY-----\nproc\n-----END RSA PRIVATE KEY-----"
    result = sanitize_payload({"key": key})
    assert result["key"] == "********"


def test_stripe_live_key_masked() -> None:
    result = sanitize_payload({"key": "sk_live_" + "a" * 24})
    assert result["key"] == "********"


def test_twilio_account_sid_masked() -> None:
    result = sanitize_payload({"key": "AC" + "a" * 32})
    assert result["key"] == "********"


def test_twilio_like_string_not_masked() -> None:
    """FP guard: short hex string starting with AC."""
    result = sanitize_payload({"key": "AC1234"})
    assert result["key"] == "AC1234"


def test_google_api_key_masked() -> None:
    result = sanitize_payload({"key": "AIza" + "a" * 35})
    assert result["key"] == "********"


def test_uppercase_api_key_field_name_redacted() -> None:
    """API_KEY (uppercase) is redacted — case-insensitive field name match."""
    result = sanitize_payload({"API_KEY": "test123"})
    assert result["API_KEY"] == "********"


def test_x_api_key_header_case_variants() -> None:
    for key in ("X-Api-Key", "x-api-key", "X-API-KEY"):
        result = sanitize_payload({key: "raw-secret"})
        assert result[key] == "********", key


def test_my_api_key_suffix_redacted() -> None:
    result = sanitize_payload({"service_api_key": "raw"})
    assert result["service_api_key"] == "********"


def test_keyboard_not_redacted_as_secret() -> None:
    result = sanitize_payload({"keyboard": "qwerty"})
    assert result["keyboard"] == "qwerty"
