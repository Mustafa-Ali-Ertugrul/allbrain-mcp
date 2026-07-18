# allbrain-sdk

Typed asynchronous Python client for a local AllBrain MCP stdio server.

```python
import asyncio
from allbrain_sdk import AllBrainClient, AssignTaskResult, CreateTaskResult

async def main():
    async with AllBrainClient(project=".", agent="code-agent", db_path=".allbrain.db") as client:
        await client.save_event("task_started", {"task": "implement auth"})
        created = await client.create_task("implement auth", priority=4)
        assigned = await client.assign_task(created.payload["task_id"])
        return assigned

state = asyncio.run(main())
```

## Resources and prompts

The server also exposes read-only MCP resources and reusable prompts. The SDK
wraps them with typed helpers:

```python
import asyncio
from allbrain_sdk import AllBrainClient, PromptMessage, ResourceRead

async def main():
    async with AllBrainClient(project=".", agent="codex") as client:
        resume: ResourceRead = await client.project_resume_raw()
        print(resume.uri, resume.text)

        prompts = await client.list_prompts()
        handoff = await client.task_handoff_prompt("task-1", "codex", reason="blocked")
        for message in handoff.messages:  # type: PromptMessage
            print(message.role, message.content)

asyncio.run(main())
```

- `read_resource(uri)` / typed shortcuts (`project_resume_raw`, `tasks_graph_raw`,
  `git_fingerprint_raw`, `session_summary`, `event_by_id`) read the server's
  read-only resources.
- `get_prompt(name, **arguments)` / typed shortcuts (`resume_project_prompt`,
  `task_handoff_prompt`, `investigate_conflict_prompt`) fetch reusable
  user/assistant prompt messages.
- `list_resources`, `list_resource_templates`, and `list_prompts` introspect
  what the server exposes.

This package is intentionally thin: it owns stdio lifecycle, validates AllBrain's response envelope, and exposes Pydantic response models. Domain logic remains in the server.
