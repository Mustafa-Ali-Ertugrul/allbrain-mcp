from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any, Self

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic import ValidationError

from allbrain_sdk.errors import AllBrainProtocolError, AllBrainToolError
from allbrain_sdk.models import (
    AllBrainConfig,
    AssignTaskResult,
    ConflictResult,
    ContextPackResult,
    CreateTaskResult,
    DecisionPipelineResult,
    EventRecord,
    ResumeProjectResult,
    TaskGraphResult,
    ToolEnvelope,
    ToolProfile,
)


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
        tool_profile: ToolProfile = "core",
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
        agent_id: str | None = None,
        branch: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
    ) -> list[EventRecord]:
        arguments: dict[str, Any] = {"limit": limit}
        if session_id is not None:
            arguments["session_id"] = session_id
        if event_type is not None:
            arguments["type"] = event_type
        if agent_id is not None:
            arguments["agent_id"] = agent_id
        if branch is not None:
            arguments["branch"] = branch
        if since is not None:
            arguments["since"] = since
        if until is not None:
            arguments["until"] = until
        payload = await self._call("list_events", arguments)
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

    async def create_task(
        self,
        goal: str,
        *,
        kind: str = "implementation",
        related_files: list[str] | None = None,
        priority: int = 3,
        task_id: str | None = None,
        agent_id: str | None = None,
        enqueue: bool = False,
    ) -> CreateTaskResult:
        arguments: dict[str, Any] = {"goal": goal, "kind": kind, "priority": priority, "enqueue": enqueue}
        if related_files is not None:
            arguments["related_files"] = related_files
        if task_id is not None:
            arguments["task_id"] = task_id
        if agent_id is not None:
            arguments["agent_id"] = agent_id
        return CreateTaskResult.model_validate(await self._call("create_task", arguments))

    async def assign_task(
        self,
        task_id: str,
        *,
        agent_id: str | None = None,
        limit: int = 5000,
    ) -> AssignTaskResult:
        arguments: dict[str, Any] = {"task_id": task_id, "limit": limit}
        if agent_id is not None:
            arguments["agent_id"] = agent_id
        return AssignTaskResult.model_validate(await self._call("assign_task", arguments))

    async def get_task_graph(self, *, limit: int = 5000) -> TaskGraphResult:
        return TaskGraphResult.model_validate(await self._call("get_task_graph", {"limit": limit}))

    async def run_decision_pipeline(
        self,
        objective: dict[str, Any],
        *,
        execute_mode: str = "event_only",
        risk_threshold: float = 0.7,
        enable_counterfactual: bool = False,
        enable_scenarios: bool = False,
        enable_foresight: bool = False,
        enable_meta_reasoning: bool = False,
        enable_uncertainty: bool = False,
        enable_information_seeking: bool = False,
        limit: int = 5000,
    ) -> DecisionPipelineResult:
        arguments = {
            "objective": objective,
            "execute_mode": execute_mode,
            "risk_threshold": risk_threshold,
            "enable_counterfactual": enable_counterfactual,
            "enable_scenarios": enable_scenarios,
            "enable_foresight": enable_foresight,
            "enable_meta_reasoning": enable_meta_reasoning,
            "enable_uncertainty": enable_uncertainty,
            "enable_information_seeking": enable_information_seeking,
            "limit": limit,
        }
        return DecisionPipelineResult.model_validate(await self._call("run_decision_pipeline", arguments))

    async def get_context_pack(
        self,
        *,
        task_id: str | None = None,
        query: str | None = None,
        window_hours: int = 24,
        limit: int = 500,
        include_git: bool = True,
        top_k: int = 5,
        event_limit: int = 30,
        session_limit: int = 20,
        session_detail_limit: int = 8,
    ) -> ContextPackResult:
        arguments = {
            "window_hours": window_hours,
            "limit": limit,
            "include_git": include_git,
            "top_k": top_k,
            "event_limit": event_limit,
            "session_limit": session_limit,
            "session_detail_limit": session_detail_limit,
        }
        if task_id is not None:
            arguments["task_id"] = task_id
        if query is not None:
            arguments["query"] = query
        return ContextPackResult.model_validate(await self._call("get_context_pack", arguments))

    async def detect_conflicts(
        self,
        *,
        limit: int = 5000,
        threshold: float = 0.7,
    ) -> ConflictResult:
        return ConflictResult.model_validate(
            await self._call("detect_conflicts", {"limit": limit, "threshold": threshold})
        )

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
