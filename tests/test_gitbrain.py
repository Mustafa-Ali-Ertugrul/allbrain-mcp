from allbrain.gitbrain import GitBrain


def test_gitbrain_returns_normalized_empty_context_for_non_repo(tmp_path) -> None:
    context = GitBrain(tmp_path).build_git_context()

    assert context["is_repo"] is False
    assert context["branch"] is None
    assert context["status"] == ""
    assert context["diff"] == ""
    assert context["files"] == []
    assert context["recent_changes"] == []
    assert context["normalized"] == {"intent": "unknown", "risk": "low", "files": []}
