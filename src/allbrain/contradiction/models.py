from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContradictionState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    context_key: str
    contradictions: list[dict] = Field(default_factory=list)
    severity_summary: dict[str, int] = Field(default_factory=dict)
    evidence_event_ids: list[str] = Field(default_factory=list)
    analysis_id: str
    template_version: int = Field(default=1, ge=1)

    @field_validator("context_key")
    @classmethod
    def _context_key_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("context_key must be a non-empty string")
        return value
