from allbrain.gitbrain import GitBrain
from allbrain.gitbrain.parser import _is_credential_var


def test_gitbrain_returns_normalized_empty_context_for_non_repo(tmp_path) -> None:
    context = GitBrain(tmp_path).build_git_context()

    assert context["is_repo"] is False
    assert context["branch"] is None
    assert context["status"] == ""
    assert context["diff"] == ""
    assert context["files"] == []
    assert context["recent_changes"] == []
    assert context["normalized"] == {"intent": "unknown", "risk": "low", "files": []}


def test_safe_git_env_strips_api_key_vars() -> None:
    assert _is_credential_var("ANTHROPIC_API_KEY")
    assert _is_credential_var("OPENAI_API_KEY")
    assert _is_credential_var("AZURE_API_KEY")
    assert _is_credential_var("GOOGLE_API_KEY")


def test_safe_git_env_strips_token_vars() -> None:
    assert _is_credential_var("AWS_BEARER_TOKEN_BEDROCK")
    assert _is_credential_var("MY_SECRET_TOKEN")
    assert _is_credential_var("TOKEN_FOO")


def test_safe_git_env_strips_credential_vars() -> None:
    assert _is_credential_var("GOOGLE_APPLICATION_CREDENTIALS")
    assert _is_credential_var("MY_CREDENTIAL")


def test_safe_git_env_preserves_essential_vars() -> None:
    assert not _is_credential_var("PATH")
    assert not _is_credential_var("HOME")
    assert not _is_credential_var("USERPROFILE")
    assert not _is_credential_var("SYSTEMROOT")
    assert not _is_credential_var("TEMP")
    assert not _is_credential_var("COMSPEC")
