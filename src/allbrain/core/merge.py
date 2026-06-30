from __future__ import annotations

from typing import Any

MERGE_STRATEGY = {
    "goal": "replace_if_present",
    "working_files": "set_union",
    "completed_tasks": "append_unique",
    "failures": "append",
    "blocked": "append",
    "open_tasks": "replace",
    "tool_usage": "append",
    "last_event_id": "replace_if_present",
    "last_working_file": "replace_if_present",
}


class StateMerger:
    def merge(self, base: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, strategy in MERGE_STRATEGY.items():
            if strategy == "replace_if_present":
                value = delta.get(key)
                if value is not None:
                    merged[key] = value
            elif strategy == "replace":
                merged[key] = delta.get(key, base.get(key))
            elif strategy == "set_union" or strategy == "append_unique":
                merged[key] = self._append_unique(base.get(key, []), delta.get(key, []))
            elif strategy == "append":
                merged[key] = list(base.get(key, [])) + list(delta.get(key, []))

        for completed_task in delta.get("completed_tasks", []):
            merged["open_tasks"] = [
                open_task for open_task in merged.get("open_tasks", []) if open_task != completed_task
            ]

        merged["event_count"] = int(base.get("event_count", 0)) + int(delta.get("event_count", 0))
        merged["git"] = delta.get("git", base.get("git", {}))
        return merged

    def _append_unique(self, left: list[Any], right: list[Any]) -> list[Any]:
        result: list[Any] = []
        for item in list(left) + list(right):
            if item not in result:
                result.append(item)
        return result
