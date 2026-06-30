from __future__ import annotations

ACTION_MAP: dict[str, list[str]] = {
    "deploy": ["run_tests", "delay_deploy", "rollback"],
    "delete": ["backup", "archive"],
}


class AlternativeGenerator:
    def generate(self, action: str) -> list[str]:
        return list(ACTION_MAP.get(action, []))
