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


def test_github_server_token_masked() -> None:
    result = sanitize_payload({"key": "ghs_" + "a" * 36})
    assert result["key"] == "********"


def test_jwt_masked() -> None:
    result = sanitize_payload({"token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dQw4w9WgXcQ"})
    assert result["token"] == "********"


def test_ssh_private_key_masked() -> None:
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----"
    result = sanitize_payload({"key": key})
    assert result["key"] == "********"


def test_stripe_live_key_masked() -> None:
    result = sanitize_payload({"key": "sk_live_" + "a" * 24})
    assert result["key"] == "********"


def test_stripe_test_key_masked() -> None:
    result = sanitize_payload({"key": "rk_test_" + "a" * 24})
    assert result["key"] == "********"


def test_twilio_sid_masked() -> None:
    result = sanitize_payload({"sid": "AC" + "a" * 30 + "12"})
    assert result["sid"] == "********"


def test_google_api_key_masked() -> None:
    result = sanitize_payload({"key": "AIzaSyD" + "a" * 32})
    assert result["key"] == "********"


def test_bearer_field_masked() -> None:
    result = sanitize_payload({"bearer": "sk-abc123"})
    assert result["bearer"] == "********"


def test_client_secret_field_masked() -> None:
    result = sanitize_payload({"client_secret": "rk_test_xyz"})
    assert result["client_secret"] == "********"


def test_authorization_field_masked() -> None:
    result = sanitize_payload({"authorization": "Bearer mytoken"})
    assert result["authorization"] == "********"


def test_apikey_field_masked() -> None:
    result = sanitize_payload({"apikey": "AIzaSy..."})
    assert result["apikey"] == "********"


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


def test_sanitize_valerr_msg_strips_input_value_with_commas() -> None:
    from allbrain.security.redaction import sanitize_valerr_msg

    # input_value containing comma and bracket chars
    msg = (
        "1 validation error for TestModel\n"
        "field\n"
        "  Input should be a valid string "
        "[type=string_type, input_value='a,]secret', input_type=str]"
    )
    cleaned = sanitize_valerr_msg(msg)
    assert "input_value=" not in cleaned
    assert "a,]secret" not in cleaned


def test_sanitize_valerr_msg_preserves_type_and_input_type() -> None:
    from allbrain.security.redaction import sanitize_valerr_msg

    msg = "[type=string_type, input_value='sk-abc', input_type=str]"
    cleaned = sanitize_valerr_msg(msg)
    assert "type=string_type" in cleaned
    assert "input_type=str" in cleaned
    assert "input_value=" not in cleaned


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


def test_header_x_api_key_masked() -> None:
    result = sanitize_payload({"headers": {"X-Api-Key": "secretvalue"}})
    assert result["headers"]["X-Api-Key"] == "********"


def test_hyphenated_api_key_field_masked() -> None:
    result = sanitize_payload({"api-key": "v"})
    assert result["api-key"] == "********"


def test_nested_password_suffix_masked() -> None:
    result = sanitize_payload({"nested": {"my_password": "p"}})
    assert result["nested"]["my_password"] == "********"


def test_url_query_sensitive_params_masked() -> None:
    url = "https://example.com/callback?api_key=plainsecret&token=abc&safe=1"
    result = sanitize_payload({"url": url})
    assert "plainsecret" not in result["url"]
    assert "token=********" in result["url"]
    assert "safe=1" in result["url"]


def test_url_openai_key_in_query_still_masked() -> None:
    secret = "sk-" + "a" * 40
    result = sanitize_payload({"url": f"https://x.com?q={secret}"})
    assert secret not in result["url"]
    assert "********" in result["url"]


def test_fp_task_key_not_masked() -> None:
    result = sanitize_payload({"task_key": "task-123", "foreign_key": "fk-9", "metric_key": "m1"})
    assert result["task_key"] == "task-123"
    assert result["foreign_key"] == "fk-9"
    assert result["metric_key"] == "m1"


def test_sanitize_text_url_query() -> None:
    from allbrain.security.redaction import sanitize_text

    text = "failed request https://api.example.com?token=supersecret&ok=1"
    cleaned = sanitize_text(text)
    assert "supersecret" not in cleaned


def test_sanitize_valerr_msg_masks_residual_secret_pattern() -> None:
    from allbrain.security.redaction import sanitize_valerr_msg

    secret = "sk-" + "b" * 40
    msg = f"boom detail without input_value but has {secret}"
    cleaned = sanitize_valerr_msg(msg)
    assert secret not in cleaned
