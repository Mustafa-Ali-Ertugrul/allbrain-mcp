from copy import deepcopy
from logging import INFO

from allbrain.security.redaction import sanitize_payload


def test_openai_key_masked() -> None:
    result = sanitize_payload({"key": "sk-" + "a" * 40})
    assert result["key"] == "********"


def test_anthropic_key_masked() -> None:
    result = sanitize_payload({"key": "sk-ant-" + "a" * 36})
    assert result["key"] == "********"


def test_anthropic_key_classified_as_anthropic(caplog) -> None:
    caplog.set_level(INFO)
    sanitize_payload({"token": "sk-ant-" + "a" * 36})

    records = [record for record in caplog.records if record.message == "secret_redacted"]
    assert records
    assert "anthropic" in records[-1].types
    assert "openai" not in records[-1].types


def test_github_pat_masked() -> None:
    result = sanitize_payload({"key": "ghp_" + "a" * 36})
    assert result["key"] == "********"


def test_github_oauth_masked() -> None:
    result = sanitize_payload({"key": "gho_" + "a" * 36})
    assert result["key"] == "********"


def test_github_user_token_masked() -> None:
    result = sanitize_payload({"key": "ghu_" + "a" * 36})
    assert result["key"] == "********"


def test_github_refresh_token_masked() -> None:
    result = sanitize_payload({"key": "ghr_" + "a" * 36})
    assert result["key"] == "********"


def test_aws_access_key_masked() -> None:
    result = sanitize_payload({"key": "AKIA" + "A" * 16})
    assert result["key"] == "********"


def test_slack_bot_token_masked() -> None:
    result = sanitize_payload({"key": "xoxb-" + "a" * 20})
    assert result["key"] == "********"


def test_nested_dict_secrets_masked() -> None:
    result = sanitize_payload({"outer": {"inner": "sk-" + "a" * 40}})
    assert result["outer"]["inner"] == "********"


def test_list_of_secrets_all_masked() -> None:
    result = sanitize_payload({"tokens": ["sk-" + "a" * 40, "ghp_" + "b" * 36]})
    assert result["tokens"] == ["********", "********"]


def test_partial_secret_in_string() -> None:
    result = sanitize_payload({"text": "token=sk-" + "a" * 40})
    assert "token=" in result["text"]
    assert "sk-" not in result["text"]
    assert result["text"] == "token=********"


def test_multiple_secrets_in_one_string() -> None:
    key_a = "sk-" + "a" * 40
    key_b = "ghp_" + "b" * 36
    result = sanitize_payload({"text": f"{key_a} {key_b}"})
    assert result["text"] == "******** ********"


def test_safe_string_unchanged() -> None:
    result = sanitize_payload({"msg": "hello world"})
    assert result["msg"] == "hello world"


def test_non_string_passthrough() -> None:
    payload = {"count": 42, "ratio": 0.5, "flag": True, "nothing": None}
    result = sanitize_payload(payload)
    assert result == payload


def test_original_payload_not_mutated() -> None:
    original = {"key": "sk-" + "a" * 40}
    expected = deepcopy(original)
    sanitize_payload(original)
    assert original == expected, "sanitize_payload mutated the input in-place"


def test_log_does_not_leak_secret(caplog) -> None:
    import logging

    caplog.set_level(INFO)
    logger = logging.getLogger("allbrain.security.redaction")
    # verify the logger exists and capture doesn't throw
    _ = logger

    payload = {"key": "sk-" + "a" * 40}
    sanitize_payload(payload)

    log_text = caplog.text
    assert "sk-" + "a" * 40 not in log_text
    assert "secret_redacted" in log_text
