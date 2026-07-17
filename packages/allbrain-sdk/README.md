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

This package is intentionally thin: it owns stdio lifecycle, validates AllBrain's response envelope, and exposes Pydantic response models. Domain logic remains in the server.
