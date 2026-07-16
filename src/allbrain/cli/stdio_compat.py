"""Compatibility shim for newline-safe MCP stdio on older Windows Python."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from io import TextIOWrapper

import anyio


def patch_stdio_newlines_for_windows() -> None:
    """Patch the tested FastMCP/MCP stdio symbols only where required.

    Python 3.14+ has native universal newline behavior on Windows.  Older
    interpreters use this narrowly-scoped compatibility adapter.  The symbol
    checks make package-internal API drift fail at startup with a useful error.
    """
    if sys.version_info >= (3, 14):
        return

    try:
        import fastmcp.server.mixins.transport as fastmcp_transport
        import mcp.server.stdio as mcp_stdio
        import mcp.types as types
        from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
        from mcp.shared.message import SessionMessage
    except ImportError as exc:  # pragma: no cover - depends on installed extras
        raise RuntimeError("The installed FastMCP/MCP packages do not expose the stdio compatibility API") from exc

    if not callable(getattr(mcp_stdio, "stdio_server", None)) or not callable(
        getattr(fastmcp_transport, "stdio_server", None)
    ):
        raise RuntimeError("The installed FastMCP/MCP packages changed their stdio transport API")
    if getattr(mcp_stdio.stdio_server, "__allbrain_lf_only__", False):
        return

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


__all__ = ["patch_stdio_newlines_for_windows"]
