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


def verify_inventory_against_server(client: Any) -> dict[str, Any]:
    """Compare the static resource/prompt inventory against a live MCP server.

    ``client`` is an ``allbrain_sdk.AllBrainClient`` (connected, or usable via
    ``async with``).  Returns a structured report with ``ok``, ``matched``,
    ``missing`` and ``extra`` lists for both resources and prompts.
    """
    import asyncio

    async def _collect() -> tuple[set[str], set[str], set[str]]:
        resources = {str(r.uri) for r in await client.list_resources()}
        templates = {str(t.uri_template) for t in await client.list_resource_templates()}
        prompts = {p.name for p in await client.list_prompts()}
        return resources | templates, prompts, set()

    try:
        live_resources, live_prompts, _ = asyncio.run(_collect())
    except Exception as exc:  # noqa: BLE001 - surface as a failed verification
        return {
            "ok": False,
            "error": str(exc),
            "resources": {"matched": [], "missing": [], "extra": []},
            "prompts": {"matched": [], "missing": [], "extra": []},
        }

    static_resources = {item["uri"] for item in RESOURCE_INVENTORY}
    static_prompts = {item["name"] for item in PROMPT_INVENTORY}

    resource_matched = sorted(static_resources & live_resources)
    resource_missing = sorted(static_resources - live_resources)
    resource_extra = sorted(live_resources - static_resources)

    prompt_matched = sorted(static_prompts & live_prompts)
    prompt_missing = sorted(static_prompts - live_prompts)
    prompt_extra = sorted(live_prompts - static_prompts)

    return {
        "ok": not resource_missing and not resource_extra and not prompt_missing and not prompt_extra,
        "resources": {
            "matched": resource_matched,
            "missing": resource_missing,
            "extra": resource_extra,
        },
        "prompts": {
            "matched": prompt_matched,
            "missing": prompt_missing,
            "extra": prompt_extra,
        },
    }
