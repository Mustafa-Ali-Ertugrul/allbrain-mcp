from __future__ import annotations

import json
from pathlib import Path


def test_glama_runtime_allows_its_container_workspace() -> None:
    config_path = Path(__file__).parents[1] / "glama.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    runtime = config["runtime"]
    assert runtime["args"][runtime["args"].index("--project") + 1] == "."
    assert runtime["args"][runtime["args"].index("--tool-profile") + 1] == "core"
    assert runtime["env"]["ALLOWED_PROJECT_ROOTS"] == "/app"
    assert config["maintainers"] == ["Mustafa-Ali-Ertugrul"]
