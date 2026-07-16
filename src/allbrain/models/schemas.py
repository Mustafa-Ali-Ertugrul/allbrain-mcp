from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from allbrain.events import EventType
from allbrain.events.schemas import normalize_event_type_name
from allbrain.security.input_guard import sanitize_payload_fields, sanitize_user_text
from allbrain.security.redaction import sanitize_payload


class UserInputError(ValueError):
    """Raised when user-provided input is invalid.
    This is distinguishable from internal ValueError by exception handler,
    so user-visible validation errors are not confused with system errors.
    """

    pass


_MAX_PAYLOAD_BYTES = 250_000
_MAX_DICT_BYTES = 50_000


def _check_null_bytes_recursive(obj: Any) -> None:
    """Reject null bytes in strings, dict keys/values, and list items."""
    if isinstance(obj, str):
        if "\x00" in obj:
            raise ValueError("null byte (\\x00) is not allowed in input")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and "\x00" in k:
                raise ValueError("null byte (\\x00) is not allowed in input")
            _check_null_bytes_recursive(v)
    elif isinstance(obj, list):
        for item in obj:
            _check_null_bytes_recursive(item)


class BaseInputModel(BaseModel):
    """Base for all input models with security validation.

    Rejects null bytes, sanitizes strings for prompt injection,
    and enforces size limits on dict fields to prevent DoS attacks.
    All MCP tool input models should inherit from this.

    Legacy/server-context fields such as ``project_path`` are stripped
    before validation: project binding always comes from BrainContext,
    never from client or wrapper kwargs. Stripping (rather than rejecting)
    keeps ``extra='forbid'`` tools compatible with older MCP clients and
    internal wrappers that still pass ``project_path=context.project_path``.
    """

    @model_validator(mode="before")
    @classmethod
    def _strip_server_context_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # Copy only when a legacy key is present to avoid unnecessary allocs.
        if "project_path" not in data:
            return data
        cleaned = dict(data)
        cleaned.pop("project_path", None)
        return cleaned

    @field_validator("*", mode="after")
    @classmethod
    def _reject_null_bytes(cls, v: Any) -> Any:
        _check_null_bytes_recursive(v)
        return v

    @field_validator("*", mode="after")
    @classmethod
    def _sanitize_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            return sanitize_user_text(v)
        if isinstance(v, dict):
            return sanitize_payload_fields(v)
        return v

    @model_validator(mode="after")
    def _check_dict_sizes(self) -> BaseInputModel:
        """Enforce size limits on all dict-typed fields."""
        import json

        for field_name, field_value in self.__dict__.items():
            if not isinstance(field_value, dict):
                continue
            raw = json.dumps(field_value)
            max_bytes = _MAX_PAYLOAD_BYTES if "payload" in field_name else _MAX_DICT_BYTES
            if len(raw) > max_bytes:
                raise ValueError(
                    f"field '{field_name}' exceeds maximum size of {max_bytes // 1000}KB (got {len(raw)} bytes)"
                )
        return self


class SaveEventInput(BaseInputModel):
    """Input model for save_event MCP tool.

    Validates event type, payload size, and optional metadata fields.
    Inherits security validation from BaseInputModel.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    type: str = Field(min_length=1)
    payload: dict[str, Any]
    file_path: str | None = Field(default=None, max_length=4000)
    source: str = Field(default="agent", min_length=1, max_length=100)
    session_id: int | None = None
    agent_id: str | None = None
    task_hint: str | None = Field(default=None, max_length=4000)
    importance: int | None = Field(default=None, ge=1, le=5)
    impact_score: float | None = Field(default=None, ge=0.0, le=1.0)
    caused_by: str | None = Field(default=None, max_length=255)
    branch: str | None = Field(default=None, max_length=255)

    @field_validator("payload")
    @classmethod
    def validate_payload_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        value = sanitize_payload(value)
        import json

        raw = json.dumps(value)
        if len(raw) > 250000:
            raise ValueError("payload exceeds maximum size of 250KB")
        return value

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return normalize_event_type_name(value)

    @model_validator(mode="after")
    def validate_task_payload(self) -> SaveEventInput:
        task_events_requiring_id = {
            EventType.TASK_ASSIGNED.value,
            EventType.SELECTION_DECISION.value,
            EventType.TASK_FAILED.value,
            EventType.TASK_DEPENDENCY_ADDED.value,
            EventType.TASK_PRIORITY_CHANGED.value,
            EventType.TASK_UPDATED.value,
            EventType.TASK_DELETED.value,
            EventType.HANDOFF_CREATED.value,
        }
        if self.type in task_events_requiring_id and not self.payload.get("task_id"):
            raise ValueError(f"{self.type} payload must include task_id")
        if self.type == EventType.TASK_DEPENDENCY_ADDED.value and not self.payload.get("depends_on"):
            raise ValueError("task_dependency_added payload must include depends_on")
        if self.type == EventType.TASK_PRIORITY_CHANGED.value and "new" not in self.payload:
            raise ValueError("task_priority_changed payload must include new")
        return self


class ListEventsInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    session_id: int | None = None
    type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_event_type_name(value)


class ResumeProjectInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    limit: int = Field(default=5000, ge=1, le=50000)
    include_git: bool = True
    use_snapshot: bool = True
    detail: str = Field(default="full", pattern="^(slim|full)$")


class CreateSnapshotInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    limit: int = Field(default=5000, ge=1, le=50000)
    force: bool = False
    include_derived: bool = False


class GitContextInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RecentChangesInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    limit: int = Field(default=10, ge=1, le=100)


class WorkSummaryInput(BaseInputModel):
    """Validated time window for cross-branch Git work summaries."""

    model_config = ConfigDict(extra="forbid", strict=True)

    since: datetime | None = None
    until: datetime | None = None
    limit: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_window(self) -> WorkSummaryInput:
        if self.since is not None and self.until is not None and self.since >= self.until:
            raise ValueError("since must be earlier than until")
        return self


class ConflictInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    limit: int = Field(default=5000, ge=1, le=50000)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class IntentInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    limit: int = Field(default=5000, ge=1, le=50000)
    include_git: bool = True
    use_snapshot: bool = True


class CreateTaskInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str | None = None
    goal: str = Field(min_length=1, max_length=10000)
    kind: str = Field(default="implementation", min_length=1, max_length=50)
    related_files: list[str] = Field(default_factory=list, max_length=50)
    priority: int = Field(default=3, ge=1, le=5)
    agent_id: str | None = Field(default=None, max_length=255)
    enqueue: bool = False

    @field_validator("related_files")
    @classmethod
    def validate_related_files(cls, v: list[str]) -> list[str]:
        for i, item in enumerate(v):
            if len(item) > 512:
                raise UserInputError(f"related_files[{i}] exceeds 512 characters")
        if len(v) > 50:
            raise UserInputError("related_files must have at most 50 items")
        return v


class AssignTaskInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str = Field(min_length=1)
    agent_id: str | None = Field(default=None, max_length=255)
    limit: int = Field(default=5000, ge=1, le=50000)


class HandoffTaskInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str = Field(min_length=1)
    from_agent: str = Field(min_length=1)
    to_agent: str | None = None
    reason: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)


class TaskDependencyInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str = Field(min_length=1)
    depends_on: str = Field(min_length=1)


class TaskPriorityInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str = Field(min_length=1)
    old: int | None = Field(default=None, ge=1, le=5)
    new: int = Field(ge=1, le=5)


class UpdateTaskInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str = Field(min_length=1)
    goal: str | None = Field(default=None, min_length=1, max_length=10000)
    kind: str | None = Field(default=None, min_length=1, max_length=50)
    related_files: list[str] | None = Field(default=None, max_length=50)

    @field_validator("related_files")
    @classmethod
    def validate_related_files(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        for i, item in enumerate(v):
            if len(item) > 512:
                raise UserInputError(f"related_files[{i}] exceeds 512 characters")
        if len(v) > 50:
            raise UserInputError("related_files must have at most 50 items")
        return v


class DeleteTaskInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    task_id: str = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=1000)


class OrchestratorInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    limit: int = Field(default=5000, ge=1, le=50000)
    include_git: bool = True
    use_snapshot: bool = True
    detail: str = Field(default="full", pattern="^(slim|full)$")


class RunDecisionPipelineInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    objective: dict[str, Any]
    execute_mode: str = Field(default="event_only", pattern="^(event_only|mock_runtime|queued_runtime)$")
    limit: int = Field(default=5000, ge=1, le=50000)
    simulate_before_execute: bool = False
    risk_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    enable_counterfactual: bool = False
    counterfactual_limit: int = Field(default=3, ge=1, le=100)
    regret_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    enable_scenarios: bool = False
    scenarios_limit: int = Field(default=4, ge=1, le=20)
    scenario_recommendation_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    enable_foresight: bool = False
    foresight_limit: int = Field(default=5, ge=1, le=20)
    max_horizon: int = Field(default=5, ge=1, le=20)
    enable_meta_reasoning: bool = False
    enable_uncertainty: bool = False
    enable_information_seeking: bool = False


class ObserveWorldInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    limit: int = Field(default=5000, ge=1, le=50000)


class SimulateActionInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class CounterfactualInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)
    counterfactual_limit: int = Field(default=3, ge=1, le=100)


class AlternativeRankingInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    actions: list[str] = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class GenerateScenariosInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)
    scenarios_limit: int = Field(default=4, ge=1, le=20)


class EvaluateScenariosInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: str = Field(min_length=1)
    scenarios: list[dict[str, Any]] = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class GenerateFuturePlansInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)
    foresight_limit: int = Field(default=5, ge=1, le=20)
    max_horizon: int = Field(default=5, ge=1, le=20)


class EvaluatePlanInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    actions: list[str] = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)
    max_horizon: int = Field(default=5, ge=1, le=20)


class ExplainDecisionInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    plan_id: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class EstimateConfidenceInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    plan_id: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class EstimateUncertaintyInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision_id: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class DetectKnowledgeGapsInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision_id: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class IdentifyInformationNeedsInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision_id: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class EstimateInformationGainInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)


class QueryBeliefInput(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    context_key: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)
    prior_alpha: float = Field(default=1.0, ge=0.0)
    prior_beta: float = Field(default=1.0, ge=0.0)


class EstimateInformationGainV2Input(BaseInputModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: str = Field(min_length=1)
    context_key: str = Field(min_length=1)
    limit: int = Field(default=5000, ge=1, le=50000)
    prior_alpha: float = Field(default=1.0, ge=0.0)
    prior_beta: float = Field(default=1.0, ge=0.0)


class EventRead(BaseModel):
    id: str
    project_id: int
    session_id: int
    agent_id: str | None = None
    type: str
    source: str
    file_path: str | None
    payload: dict[str, Any]
    task_hint: str | None
    importance: int | None
    impact_score: float | None = None
    caused_by: str | None = None
    branch: str | None = None
    created_at: datetime
    payload_version: int = Field(default=1, ge=1)
    stream_position: int | None = None


class ToolResult(BaseModel):
    ok: bool
    data: Any | None = None
    error: str | None = None
    error_code: str | None = None
