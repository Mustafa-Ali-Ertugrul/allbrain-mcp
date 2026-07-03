# allbrain-sdk

Typed asynchronous Python client for a local AllBrain MCP stdio server.

```python
import asyncio
from allbrain_sdk import AllBrainClient

async def main():
    async with AllBrainClient(project=".", agent="code-agent", db_path=".allbrain.db") as client:
        await client.save_event("task_started", {"task": "implement auth"})
        return await client.resume_project(include_git=False)

state = asyncio.run(main())
```

This package is intentionally thin: it owns stdio lifecycle, validates AllBrain's response envelope, and exposes Pydantic response models. Domain logic remains in the server.
