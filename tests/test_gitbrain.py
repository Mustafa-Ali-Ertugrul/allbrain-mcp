import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta, timezone

from git import Repo

from allbrain.domains.memory.gitbrain import GitBrain
from allbrain.domains.memory.gitbrain.parser import _is_credential_var


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


def test_work_summary_includes_commits_from_all_branches(tmp_path) -> None:
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Tester").set_value("user", "email", "tester@example.com").release()
    main_file = tmp_path / "main.txt"
    main_file.write_text("main\n", encoding="utf-8")
    repo.index.add(["main.txt"])
    first = repo.index.commit("main work")

    feature = repo.create_head("feature")
    feature.checkout()
    feature_file = tmp_path / "feature.txt"
    feature_file.write_text("feature\n", encoding="utf-8")
    repo.index.add(["feature.txt"])
    second = repo.index.commit("feature work")

    since = datetime.fromtimestamp(first.committed_date, UTC) - timedelta(seconds=1)
    until = datetime.fromtimestamp(second.committed_date, UTC) + timedelta(seconds=1)
    summary = GitBrain(tmp_path).get_work_summary(since=since, until=until)

    assert summary["commit_count"] == 2
    assert summary["work_commit_count"] == 2
    assert summary["merge_commit_count"] == 0
    assert summary["files"] == ["feature.txt", "main.txt"]
    assert summary["additions"] == 2
    assert summary["deletions"] == 0
    assert summary["truncated"] is False


class TestGitEnvSandbox:
    """_git_env context manager: env isolation and thread safety."""

    def test_env_sandbox_restores_fully(self) -> None:
        """After _git_env exits, os.environ matches the original."""
        brain = GitBrain(".")
        original = dict(os.environ)
        # Set a distinct marker to verify restore
        os.environ["_ALLBRAIN_TEST_MARKER"] = "should_persist"
        try:
            with brain._git_env():
                # Inside: safe env vars expected
                assert "PATH" in os.environ
                assert "GIT_TERMINAL_PROMPT" in os.environ
            # Outside: marker restored (non-credential → passes safe_git_env)
            assert os.environ.get("_ALLBRAIN_TEST_MARKER") == "should_persist"
            for k, v in original.items():
                assert os.environ.get(k) == v, f"Mismatch for {k}"
        finally:
            os.environ.pop("_ALLBRAIN_TEST_MARKER", None)

    def test_env_sandbox_strips_cred_vars(self) -> None:
        """Credentials set in env before _git_env are excluded inside."""
        brain = GitBrain(".")
        os.environ["_ALLBRAIN_TEST_TOKEN"] = "sk-secret-12345"
        try:
            with brain._git_env():
                assert "_ALLBRAIN_TEST_TOKEN" not in os.environ
            # Restored after exit
            assert os.environ["_ALLBRAIN_TEST_TOKEN"] == "sk-secret-12345"
        finally:
            os.environ.pop("_ALLBRAIN_TEST_TOKEN", None)

    def test_concurrent_env_sandbox_no_crash(self) -> None:
        """Multiple threads calling _git_env simultaneously must not raise."""
        brain = GitBrain(".")

        def run_sandbox(delay: float) -> None:
            time.sleep(delay)
            with brain._git_env():
                # Inside sandbox: only safe env
                assert "GIT_TERMINAL_PROMPT" in os.environ
                time.sleep(0.005)

        errors: list[Exception] = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs = [pool.submit(run_sandbox, i * 0.01) for i in range(4)]
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception as exc:
                    errors.append(exc)

        assert not errors, f"Concurrent _git_env raised: {errors}"


def test_work_summary_reports_truncation(tmp_path) -> None:
    repo = Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Tester").set_value("user", "email", "tester@example.com").release()
    for index in range(2):
        path = tmp_path / f"{index}.txt"
        path.write_text(str(index), encoding="utf-8")
        repo.index.add([path.name])
        repo.index.commit(f"work {index}")

    summary = GitBrain(tmp_path).get_work_summary(limit=1)

    assert summary["commit_count"] == 1
    assert summary["truncated"] is True
