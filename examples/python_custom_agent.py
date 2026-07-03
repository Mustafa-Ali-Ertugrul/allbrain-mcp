"""Minimal custom Python agent using AllBrain over MCP stdio."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def run(project: Path, agent: str, db_path: Path | None) -> dict[str, object]:
    args = ["run", "allbrain", "start", "--project", str(project), "--agent", agent]
    if db_path is not None:
        args.extend(["--db-path", str(db_path)])
    transport = StdioTransport("uv", args, cwd=str(Path(__file__).resolve().parents[1]))
    async with Client(transport) as client:
        saved = await client.call_tool(
            "save_event",
            {"type": "task_started", "payload": {"task": "index repository"}},
        )
        if not isinstance(saved.data, dict) or not saved.data.get("ok"):
            raise RuntimeError(f"save_event failed: {saved.data}")
        resumed = await client.call_tool("resume_project", {"include_git": False})
        if not isinstance(resumed.data, dict) or not resumed.data.get("ok"):
            raise RuntimeError(f"resume_project failed: {resumed.data}")
        return {"saved": saved.data["data"], "resumed": resumed.data["data"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--agent", default="python-agent")
    parser.add_argument("--db-path", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.project, args.agent, args.db_path)), default=str))


if __name__ == "__main__":
    main()
