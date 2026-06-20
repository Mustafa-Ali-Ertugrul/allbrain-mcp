from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


DEFAULT_AGENT_VERSION = "1.0.0"
UNHEALTHY_FAILURE_THRESHOLD = 5


@dataclass(frozen=True)
class AgentCapability:
    domain: str
    skills: set[str]


@dataclass(frozen=True)
class TaskRequirements:
    domain: str
    required_skills: set[str]

    @classmethod
    def from_task(cls, task: dict[str, Any]) -> "TaskRequirements":
        domain = str(task.get("domain") or "software")
        required_skills = task.get("required_skills") or task.get("skills") or []
        if isinstance(required_skills, str):
            required_skills = [required_skills]
        if not required_skills:
            task_type = task.get("task_type") or task.get("kind")
            if isinstance(task_type, str) and task_type:
                required_skills = [task_type]
        return cls(domain=domain, required_skills={str(skill) for skill in required_skills})


@dataclass(frozen=True)
class AgentHealth:
    consecutive_failures: int = 0
    last_failure_at: datetime | None = None
    last_failure_reason: str | None = None
    in_probe_mode: bool = False
    healthy: bool = True

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any], *, in_probe_mode: bool = False) -> "AgentHealth":
        consecutive_failures = int(metrics.get("consecutive_failures", 0) or 0)
        return cls(
            consecutive_failures=consecutive_failures,
            last_failure_at=_parse_datetime(metrics.get("last_failure_at")),
            last_failure_reason=_string_or_none(metrics.get("last_failure_reason")),
            in_probe_mode=in_probe_mode,
            healthy=consecutive_failures < UNHEALTHY_FAILURE_THRESHOLD,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "consecutive_failures": self.consecutive_failures,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
            "last_failure_reason": self.last_failure_reason,
            "in_probe_mode": self.in_probe_mode,
            "healthy": self.healthy,
        }


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    version: str = DEFAULT_AGENT_VERSION
    capabilities: tuple[AgentCapability, ...] = field(default_factory=tuple)
    health: AgentHealth = field(default_factory=AgentHealth)
    cost: dict[str, float] = field(default_factory=dict)
    legacy_skill_weights: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_raw(
        cls,
        agent_id: str,
        raw: Any,
        metrics: dict[str, Any] | None = None,
    ) -> "AgentProfile":
        raw = raw if isinstance(raw, dict) else {"software": raw}
        cost_raw = raw.get("cost", {}) if isinstance(raw.get("cost"), dict) else {}
        return cls(
            agent_id=agent_id,
            version=str(raw.get("version") or DEFAULT_AGENT_VERSION),
            capabilities=tuple(_normalize_capabilities(raw.get("capabilities", raw))),
            health=AgentHealth.from_metrics(metrics or {}),
            cost={
                "avg_latency_ms": float(cost_raw.get("avg_latency_ms", 0.0) or 0.0),
                "avg_cost": float(cost_raw.get("avg_cost", 0.0) or 0.0),
            },
            legacy_skill_weights=_legacy_skill_weights(raw.get("capabilities", raw)),
        )

    def capability_score(self, task: TaskRequirements) -> float:
        if self.legacy_skill_weights and task.domain == "software" and task.required_skills:
            matched_weight = sum(
                self.legacy_skill_weights.get(skill, 0.0) for skill in task.required_skills
            )
            return min(1.0, matched_weight / (10 * len(task.required_skills)))
        return max((_match_score(capability, task) for capability in self.capabilities), default=0.0)

    def capabilities_by_domain(self) -> dict[str, list[str]]:
        return {capability.domain: sorted(capability.skills) for capability in self.capabilities}


def _match_score(agent: AgentCapability, task: TaskRequirements) -> float:
    if agent.domain != task.domain:
        return 0.0
    if not task.required_skills:
        return 1.0
    return len(task.required_skills & agent.skills) / len(task.required_skills)


def _normalize_capabilities(raw: Any) -> list[AgentCapability]:
    if isinstance(raw, list):
        return [AgentCapability(domain="software", skills={str(skill) for skill in raw})]
    if not isinstance(raw, dict):
        return []
    if isinstance(raw.get("domain"), str) and isinstance(raw.get("skills"), list):
        return [
            AgentCapability(
                domain=str(raw["domain"]),
                skills={str(skill) for skill in raw["skills"]},
            )
        ]
    legacy_skills = {
        str(skill)
        for skill, weight in raw.items()
        if skill not in {"version", "health", "cost"}
        and isinstance(weight, int | float)
        and weight > 0
    }
    if legacy_skills:
        return [AgentCapability(domain="software", skills=legacy_skills)]
    capabilities: list[AgentCapability] = []
    for domain, skills in raw.items():
        if domain in {"version", "health", "cost"}:
            continue
        if isinstance(skills, str):
            capabilities.append(AgentCapability(domain=str(domain), skills={skills}))
        elif isinstance(skills, list):
            capabilities.append(
                AgentCapability(domain=str(domain), skills={str(skill) for skill in skills})
            )
    return capabilities


def _legacy_skill_weights(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(skill): float(weight)
        for skill, weight in raw.items()
        if skill not in {"version", "health", "cost"} and isinstance(weight, int | float)
    }


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
