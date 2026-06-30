from __future__ import annotations

DEPLOY_PLANS: list[list[str]] = [
    ["deploy"],
    ["run_tests", "deploy"],
    ["run_tests", "fix_failures", "deploy"],
    ["run_tests", "fix_failures", "deploy", "monitor"],
]


class ActionPlanner:
    def generate(self, action: str) -> list[list[str]]:
        if action == "deploy":
            return [list(plan) for plan in DEPLOY_PLANS]
        return []
