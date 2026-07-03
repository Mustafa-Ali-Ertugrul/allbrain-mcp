# Custom-agent integration

AllBrain is a local MCP stdio server. The client starts `allbrain`, completes the MCP handshake, calls tools, and owns the child process until the connection closes. Protocol frames use stdout; server diagnostics use stderr.

For Python applications, the repository's experimental [`allbrain-sdk`](../packages/allbrain-sdk/README.md) packages this lifecycle and validates responses with Pydantic. The raw FastMCP example below remains useful when implementing another language client or debugging the wire contract.

## Python

FastMCP is already installed with AllBrain:

```python
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():
    transport = StdioTransport("uv", ["run", "allbrain", "start", "--project", ".", "--agent", "python-agent"])
    async with Client(transport) as client:
        saved = await client.call_tool("save_event", {
            "type": "task_started", "payload": {"task": "index repository"}
        })
        if not saved.data.get("ok"):
            raise RuntimeError(saved.data["error"])
        resumed = await client.call_tool("resume_project", {"include_git": False})
        print(resumed.data)

asyncio.run(main())
```

## Node.js / TypeScript

Install the official MCP client with `npm install @modelcontextprotocol/client`, then run:

```typescript
import { Client } from "@modelcontextprotocol/client";
import { StdioClientTransport } from "@modelcontextprotocol/client/stdio";

const client = new Client({ name: "node-agent", version: "1.0.0" });
const transport = new StdioClientTransport({
  command: "uv",
  args: ["run", "allbrain", "start", "--project", ".", "--agent", "node-agent"],
});

try {
  await client.connect(transport);
  const saved = await client.callTool({
    name: "save_event", arguments: { type: "task_started", payload: { task: "index repository" } },
  });
  const resumed = await client.callTool({ name: "resume_project", arguments: { include_git: false } });
  console.dir(saved.structuredContent ?? saved.content);
  console.dir(resumed.structuredContent ?? resumed.content);
} finally {
  await client.close();
}
```

The stdio transport launches the server. Do not start a second `allbrain` process for the same client connection.

## Tool contracts

### `save_event`

The smallest valid request is:

```json
{"type":"task_started","payload":{"task":"index repository"}}
```

`type` must be one of AllBrain's registered event types. `payload` is a JSON object with a serialized maximum size of 250 KB. Optional metadata includes `file_path`, `source`, `session_id`, `task_hint`, `importance`, `impact_score`, `caused_by`, and `branch`.

### `resume_project`

```json
{"limit":5000,"include_git":false,"use_snapshot":true}
```

The call rebuilds the project view from the selected event store and returns the shared multi-agent state.

## Errors and lifecycle

Tool results use the AllBrain envelope `{"ok": boolean, "data": ..., "error": ...}` inside the MCP result. A successful MCP exchange can therefore still contain `ok: false`; clients must check both the protocol error state and the AllBrain envelope.

Use one explicit project path and database target across clients that must share memory. Set `ALLBRAIN_DATABASE_URL` before launching the custom agent for PostgreSQL, or use a common `--db-path` for SQLite. Close the MCP client to terminate the child process and release database handles.

The TypeScript transport and `callTool` shape follow the [official MCP client guide](https://ts.sdk.modelcontextprotocol.io/v2/get-started/first-client.html).
