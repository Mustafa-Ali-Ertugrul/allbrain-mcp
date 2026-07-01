from __future__ import annotations

import random
from pathlib import Path

from allbrain.server.app import resume_project_impl, save_event_impl
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from tests._helpers import make_context_from_repo


def test_stress_1000_events_random_churn_and_5_agent_switches(tmp_path: Path) -> None:
    rng = random.Random(20260617)
    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()

    codex_context = make_context_from_repo(repo, project_root, "codex")
    files = [f"module_{index}.py" for index in range(40)]
    tasks = [f"Task {index}" for index in range(25)]
    expected_files: set[str] = set()
    expected_completed: set[str] = set()
    expected_failures = 0

    for index in range(1000):
        roll = rng.random()
        if roll < 0.55:
            file_path = rng.choice(files)
            expected_files.add(file_path)
            result = save_event_impl(
                codex_context,
                type="file_modified",
                payload={"index": index},
                file_path=file_path,
            )
        elif roll < 0.72:
            task = rng.choice(tasks)
            result = save_event_impl(
                codex_context,
                type="task_started",
                payload={"task": task, "index": index},
            )
        elif roll < 0.88:
            task = rng.choice(tasks)
            expected_completed.add(task)
            result = save_event_impl(
                codex_context,
                type="task_completed",
                payload={"task": task, "index": index},
            )
        else:
            expected_failures += 1
            result = save_event_impl(
                codex_context,
                type="failure",
                payload={"error": f"Injected failure {index}", "index": index},
            )
        assert result.ok, result.error

    resume_event_counts = []
    tool_usage_counts = []
    for agent_index, agent in enumerate(["claude", "antigravity", "opencode", "codex-2", "claude-2"]):
        context = make_context_from_repo(repo, project_root, agent)
        result = resume_project_impl(context, include_git=False, limit=5000)
        assert result.ok, result.error

        data = result.data
        resume_event_counts.append(data["event_count"])
        tool_usage_counts.append(len(data["tool_usage"]))

        assert len(data["working_files"]) == len(set(data["working_files"]))
        assert set(data["working_files"]) == expected_files
        assert len(data["completed"]) == len(set(data["completed"]))
        assert set(data["completed"]).issubset(expected_completed)
        assert len(data["failures"]) == expected_failures
        assert data["next_step"] in {
            "Investigate the latest failure",
            "Start next task",
        } or data["next_step"].startswith("Continue task:")
        assert data["git"] == {}
        assert data["last_event_id"] is not None
        assert data["event_count"] == 2000 + agent_index

    assert resume_event_counts == [2000, 2001, 2002, 2003, 2004]
    assert tool_usage_counts == [1000, 1001, 1002, 1003, 1004]
