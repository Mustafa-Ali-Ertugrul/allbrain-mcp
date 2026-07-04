from __future__ import annotations

from pathlib import Path
from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.gitbrain import GitBrain


class ContextBuilder:
    def build(
        self,
        *,
        events: list[EventRead],
        project_path: str | Path,
        include_git: bool = True,
    ) -> dict[str, Any]:
        git_context = GitBrain(project_path).build_git_context() if include_git else {}
        return {"events": events, "git": git_context}
