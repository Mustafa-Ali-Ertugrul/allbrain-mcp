from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp.types import TextContent
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
    PromptDescriptor,
    PromptMessage,
    PromptResult,
    ResourceDescriptor,
    ResourceRead,
    ResourceTemplateDescriptor,
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
        # list_events now returns a ListEventsPage dict (events key contains the list)
        events = payload.get("events", []) if isinstance(payload, dict) else payload
        return [EventRecord.model_validate(item) for item in events]

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

    async def list_resources(self) -> list[ResourceDescriptor]:
        if self._client is None:
            raise AllBrainProtocolError("Client is not connected; use 'async with' or await connect()")
        resources = await self._client.list_resources()
        return [
            ResourceDescriptor(
                uri=str(item.uri),
                name=item.name,
                description=item.description,
                mime_type=item.mimeType,
            )
            for item in resources
        ]

    async def list_resource_templates(self) -> list[ResourceTemplateDescriptor]:
        if self._client is None:
            raise AllBrainProtocolError("Client is not connected; use 'async with' or await connect()")
        templates = await self._client.list_resource_templates()
        return [
            ResourceTemplateDescriptor(
                uri_template=str(item.uriTemplate),
                name=item.name,
                description=item.description,
                mime_type=item.mimeType,
            )
            for item in templates
        ]

    async def list_prompts(self) -> list[PromptDescriptor]:
        if self._client is None:
            raise AllBrainProtocolError("Client is not connected; use 'async with' or await connect()")
        prompts = await self._client.list_prompts()
        return [
            PromptDescriptor(
                name=item.name,
                description=item.description,
                arguments=[arg.model_dump() for arg in item.arguments] if item.arguments else [],
            )
            for item in prompts
        ]

    async def read_resource(self, uri: str) -> ResourceRead:
        if self._client is None:
            raise AllBrainProtocolError("Client is not connected; use 'async with' or await connect()")
        contents = await self._client.read_resource(uri)
        first = contents[0] if contents else None
        if first is None:
            raise AllBrainProtocolError(f"MCP resource '{uri}' returned no content")
        return ResourceRead(
            uri=str(getattr(first, "uri", uri)),
            mime_type=getattr(first, "mimeType", None),
            text=getattr(first, "text", None),
            blob=getattr(first, "blob", None),
        )

    async def get_prompt(self, name: str, /, **arguments: Any) -> PromptResult:
        if self._client is None:
            raise AllBrainProtocolError("Client is not connected; use 'async with' or await connect()")
        result = await self._client.get_prompt(name, arguments=arguments or None)
        parsed_messages: list[PromptMessage] = []
        for message in result.messages:
            content = message.content
            if isinstance(content, TextContent):
                text = content.text
            else:
                text = json.dumps(content.model_dump(mode="json"), default=str, sort_keys=True)
            parsed_messages.append(PromptMessage(role=message.role, content=text))
        return PromptResult(
            name=name,
            description=result.description,
            messages=parsed_messages,
        )

    async def project_resume_raw(self) -> ResourceRead:
        return await self.read_resource("project://resume")

    async def tasks_graph_raw(self) -> ResourceRead:
        return await self.read_resource("tasks://graph")

    async def git_fingerprint_raw(self) -> ResourceRead:
        return await self.read_resource("git://fingerprint")

    async def session_summary(self, session_id: int) -> ResourceRead:
        return await self.read_resource(f"session://{session_id}/summary")

    async def event_by_id(self, event_id: str) -> ResourceRead:
        return await self.read_resource(f"event://{event_id}")

    async def resume_project_prompt(self, limit: int = 5000) -> PromptResult:
        return await self.get_prompt("resume_project", limit=limit)

    async def task_handoff_prompt(
        self,
        task_id: str,
        from_agent: str,
        reason: str | None = None,
    ) -> PromptResult:
        arguments: dict[str, Any] = {"task_id": task_id, "from_agent": from_agent}
        if reason is not None:
            arguments["reason"] = reason
        return await self.get_prompt("task_handoff", **arguments)

    async def investigate_conflict_prompt(self, session_id: int) -> PromptResult:
        return await self.get_prompt("investigate_conflict", session_id=session_id)

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
