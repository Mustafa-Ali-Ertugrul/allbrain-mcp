from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Annotated

import anyio
import typer
from rich.console import Console

from allbrain.config import canonicalize_project_path, default_db_path
from allbrain.server import BrainContext, create_mcp_server
from allbrain.server.lifecycle import reconcile_stale_sessions
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from allbrain.storage.history_repair import HistoryRepairer, backup_sqlite

app = typer.Typer(no_args_is_help=True)
console = Console(stderr=True)


@app.callback()
def main() -> None:
    """AllBrain MCP command line interface."""


@app.command()
def install(
    clients: Annotated[list[str] | None, typer.Argument(help="Clients to configure (default: all)")] = None,
    all_clients: Annotated[bool, typer.Option("--all", help="Configure every supported client")] = False,
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root to bind.")] = Path("."),
    isolate: Annotated[bool, typer.Option("--isolate", help="Use separate DB per client")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show changes without writing")] = False,
    verify: Annotated[bool, typer.Option("--verify", help="Run MCP handshake after config")] = False,
) -> None:
    """Configure MCP clients to connect to AllBrain.

    Supported clients: codex, claude, claude-desktop, opencode, gemini,
    antigravity, vscode, cursor, windsurf, zed, kiro.
    """
    from allbrain.install import main as installer_main

    args = ["--project", str(project)]
    if isolate:
        args.append("--isolate")
    if dry_run:
        args.append("--dry-run")
    if verify:
        args.append("--verify")
    if all_clients:
        args.append("--all")
    if clients:
        args.extend(clients)
    installer_main(args)


@app.command()
def start(
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root to bind.")] = Path("."),
    agent: Annotated[str, typer.Option("--agent", "-a", help="Agent name for the session.")] = "unknown",
    db_path: Annotated[
        Path | None,
        typer.Option("--db-path", help="SQLite DB path. Defaults to ~/.allbrain/allbrain.db."),
    ] = None,
    tool_profile: Annotated[
        str | None,
        typer.Option("--tool-profile", help="Tool profile: 'full' or 'core'."),
    ] = None,
) -> None:
    run_mcp_server(project=project, agent=agent, db_path=db_path, tool_profile=tool_profile or "full")


def run_mcp_server(project: Path, agent: str, db_path: Path | None, tool_profile: str = "full") -> None:
    resolved_db_path = db_path or default_db_path()
    project_path = canonicalize_project_path(project)
    engine = create_engine_for_path(resolved_db_path)
    init_db(engine)
    repository = BrainRepository(engine)
    context = BrainContext(
        repository=repository,
        project_path=project_path,
        active_session=None,
        agent_name=agent,
        central_audit_enabled=True,
    )
    reconciled = reconcile_stale_sessions(context)
    if reconciled:
        console.log(f"Reconciled {len(reconciled)} stale AllBrain session(s)")
    console.log(f"AllBrain MCP started for {project_path}")
    server = create_mcp_server(context, tool_profile=tool_profile)
    _patch_stdio_newlines_for_windows()
    try:
        server.run(transport="stdio", show_banner=False)
    finally:
        repository.close()


@app.command("repair-history")
def repair_history(
    project: Annotated[Path, typer.Option("--project", "-p", help="Project root to repair.")] = Path("."),
    db_path: Annotated[Path | None, typer.Option("--db-path", help="Shared SQLite database.")] = None,
    source_db: Annotated[
        list[Path] | None,
        typer.Option("--source-db", help="Agent database to merge; repeat for multiple files."),
    ] = None,
    apply: Annotated[bool, typer.Option("--apply", help="Apply changes; default is dry-run.")] = False,
) -> None:
    resolved_db = (db_path or default_db_path()).expanduser().resolve()
    project_path = canonicalize_project_path(project)
    sources = list(source_db or sorted(resolved_db.parent.glob(".allbrain-*.db")))
    engine = create_engine_for_path(resolved_db)
    init_db(engine)
    repairer = HistoryRepairer(engine, project_path=project_path, target_path=resolved_db)
    report = repairer.inspect(sources)
    console.print_json(data={"mode": "apply" if apply else "dry-run", **report})
    if not apply:
        engine.dispose()
        return
    backup = backup_sqlite(resolved_db)
    result = repairer.apply(sources)
    console.print_json(data={"backup": str(backup), **result})
    engine.dispose()


def _patch_stdio_newlines_for_windows() -> None:
    """Keep MCP JSON-RPC frames LF-delimited on Windows stdio.

    Python 3.14+ ships native universal newline support on Windows
    (https://github.com/python/cpython/issues/108196), so the monkey-patch
    is only required on older interpreters.
    """
    if sys.version_info >= (3, 14):
        return

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
            stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace", newline="\n"))
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
