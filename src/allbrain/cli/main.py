from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from io import TextIOWrapper
from pathlib import Path

import anyio
import typer
from rich.console import Console

from allbrain.config import canonicalize_project_path, default_db_path
from allbrain.server import BrainContext, create_mcp_server
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)


@app.callback()
def main() -> None:
    """AllBrain MCP command line interface."""


@app.command()
def start(
    project: Path = typer.Option(Path("."), "--project", "-p", help="Project root to bind."),
    agent: str = typer.Option("unknown", "--agent", "-a", help="Agent name for the session."),
    db_path: Path | None = typer.Option(None, "--db-path", help="SQLite DB path. Defaults to ~/.allbrain/allbrain.db."),
) -> None:
    run_mcp_server(project=project, agent=agent, db_path=db_path)


def run_mcp_server(project: Path, agent: str, db_path: Path | None) -> None:
    resolved_db_path = db_path or default_db_path()
    project_path = canonicalize_project_path(project)
    engine = create_engine_for_path(resolved_db_path)
    init_db(engine)
    repository = BrainRepository(engine)
    active_session = repository.create_session(project_path=project_path, agent_name=agent)
    context = BrainContext(
        repository=repository,
        project_path=project_path,
        active_session=active_session,
    )
    console.log(f"AllBrain MCP started for {project_path}")
    server = create_mcp_server(context)
    _patch_stdio_newlines_for_windows()
    server.run(transport="stdio", show_banner=False)


def _patch_stdio_newlines_for_windows() -> None:
    """Keep MCP JSON-RPC frames LF-delimited on Windows stdio."""
    import fastmcp.server.mixins.transport as fastmcp_transport
    import mcp.server.stdio as mcp_stdio
    import mcp.types as types
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    from mcp.shared.message import SessionMessage

    if getattr(mcp_stdio.stdio_server, "__allbrain_lf_only__", False):
        return

    # Tested against FastMCP 3.4.2 / MCP stdio internals from uv.lock.
    # Recheck this patch when either package updates.
    @asynccontextmanager
    async def lf_stdio_server(
        stdin: anyio.AsyncFile[str] | None = None,
        stdout: anyio.AsyncFile[str] | None = None,
    ):
        if not stdin:
            stdin = anyio.wrap_file(
                TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace", newline="\n")
            )
        if not stdout:
            stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n"))

        read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
        read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
        write_stream: MemoryObjectSendStream[SessionMessage]
        write_stream_reader: MemoryObjectReceiveStream[SessionMessage]
        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

        async def stdin_reader() -> None:
            try:
                async with read_stream_writer:
                    async for line in stdin:
                        try:
                            message = types.JSONRPCMessage.model_validate_json(line)
                        except Exception as exc:
                            await read_stream_writer.send(exc)
                            continue

                        await read_stream_writer.send(SessionMessage(message))
            except anyio.ClosedResourceError:
                await anyio.lowlevel.checkpoint()

        async def stdout_writer() -> None:
            try:
                async with write_stream_reader:
                    async for session_message in write_stream_reader:
                        json = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                        await stdout.write(json + "\n")
                        await stdout.flush()
            except anyio.ClosedResourceError:
                await anyio.lowlevel.checkpoint()

        async with anyio.create_task_group() as tg:
            tg.start_soon(stdin_reader)
            tg.start_soon(stdout_writer)
            yield read_stream, write_stream

    lf_stdio_server.__allbrain_lf_only__ = True
    mcp_stdio.stdio_server = lf_stdio_server
    fastmcp_transport.stdio_server = lf_stdio_server


if __name__ == "__main__":
    app()
