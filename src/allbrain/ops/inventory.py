"""Static inventory helpers for MCP resources and prompts.

Used by the doctor CLI and operational tooling to list registered
resources and prompts without requiring a live MCP server.
"""

from __future__ import annotations

from typing import Any

RESOURCE_INVENTORY: list[dict[str, Any]] = [
    {
        "uri": "project://resume",
        "name": "project_resume",
        "description": "Project event counts, session count, and agent count",
    },
    {
        "uri": "tasks://graph",
        "name": "tasks_graph",
        "description": "Task state projection and agent metrics",
    },
    {
        "uri": "git://fingerprint",
        "name": "git_fingerprint",
        "description": "Git baseline fingerprint for the project",
    },
    {
        "uri": "session://{session_id}/summary",
        "name": "session_summary",
        "description": "Session event summary by session ID",
    },
    {
        "uri": "event://{event_id}",
        "name": "event_by_id",
        "description": "Full event record by event ID",
    },
]

PROMPT_INVENTORY: list[dict[str, Any]] = [
    {
        "name": "resume_project",
        "description": "Generate user/assistant messages to resume project work",
        "parameters": ["limit"],
    },
    {
        "name": "task_handoff",
        "description": "Generate user/assistant messages for agent task handoff",
        "parameters": ["task_id", "from_agent", "reason"],
    },
    {
        "name": "investigate_conflict",
        "description": "Generate user/assistant messages to investigate a conflict session",
        "parameters": ["session_id"],
    },
]


def build_resource_inventory(context: Any = None) -> list[dict[str, Any]]:
    return RESOURCE_INVENTORY


def build_prompt_inventory(context: Any = None) -> list[dict[str, Any]]:
    return PROMPT_INVENTORY
