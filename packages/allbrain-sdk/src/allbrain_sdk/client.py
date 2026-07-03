from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any, Self

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic import ValidationError

from allbrain_sdk.errors import AllBrainProtocolError, AllBrainToolError
from allbrain_sdk.models import AllBrainConfig, EventRecord, ResumeProjectResult, ToolEnvelope


class AllBrainClient:
    """Typed async facade over an AllBrain MCP stdio process."""

    def __init__(
        self,
        *,
        project: str | Path = ".",
        agent: str,
        db_path: str | Path | None = None,
        command: str = "uv",
        server_cwd: str | Path | None = None,
        tool_profile: str = "core",
        timeout_seconds: float = 120.0,
    ) -> None:
        self.config = AllBrainConfig(
            project=Path(project),
            agent=agent,
            db_path=Path(db_path) if db_path is not None else None,
            command=command,
            server_cwd=Path(server_cwd) if server_cwd is not None else None,
            tool_profile=tool_profile,
            timeout_seconds=timeout_seconds,
        )
        self._client: Client | None = None

    async def __aenter__(self) -> Self:
        return await self.connect()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._client is not None:
            client, self._client = self._client, None
            await client.__aexit__(exc_type, exc_value, traceback)

    async def connect(self) -> Self:
        if self._client is not None:
            return self
        args = [
            "run",
            "allbrain",
            "start",
            "--project",
            str(self.config.project),
            "--agent",
            self.config.agent,
            "--tool-profile",
            self.config.tool_profile,
        ]
        if self.config.db_path is not None:
            args.extend(["--db-path", str(self.config.db_path)])
        transport = StdioTransport(
            self.config.command,
            args,
            cwd=str(self.config.server_cwd) if self.config.server_cwd is not None else None,
        )
        client = Client(transport, timeout=self.config.timeout_seconds)
        await client.__aenter__()
        self._client = client
        return self

    async def close(self) -> None:
        await self.__aexit__(None, None, None)

    async def save_event(
        self,
        event_type: str,
        data: dict[str, Any],
        **metadata: Any,
    ) -> EventRecord:
        arguments = {"type": event_type, "payload": data}
        arguments.update({key: value for key, value in metadata.items() if value is not None})
        payload = await self._call("save_event", arguments)
        return EventRecord.model_validate(payload)

    async def list_events(
        self,
        *,
        session_id: int | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[EventRecord]:
        payload = await self._call(
            "list_events",
            {"session_id": session_id, "type": event_type, "limit": limit},
        )
        return [EventRecord.model_validate(item) for item in payload]

    async def resume_project(
        self,
        *,
        limit: int = 5000,
        include_git: bool = True,
        use_snapshot: bool = True,
    ) -> ResumeProjectResult:
        payload = await self._call(
            "resume_project",
            {"limit": limit, "include_git": include_git, "use_snapshot": use_snapshot},
        )
        return ResumeProjectResult.model_validate(payload)

    async def _call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if self._client is None:
            raise AllBrainProtocolError("Client is not connected; use 'async with' or await connect()")
        result = await self._client.call_tool(tool_name, arguments)
        if result.is_error:
            raise AllBrainProtocolError(f"MCP tool '{tool_name}' failed: {result.content}")
        try:
            envelope = ToolEnvelope[Any].model_validate(result.data)
        except ValidationError as exc:
            raise AllBrainProtocolError(f"MCP tool '{tool_name}' returned an invalid AllBrain envelope") from exc
        if not envelope.ok:
            raise AllBrainToolError(envelope.error or f"AllBrain tool '{tool_name}' failed")
        if envelope.data is None:
            raise AllBrainProtocolError(f"AllBrain tool '{tool_name}' returned no data")
        return envelope.data
