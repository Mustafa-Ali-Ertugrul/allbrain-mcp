from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from allbrain.domains.collaboration.agents.adapter import AgentAdapter, ExecutionContext
from allbrain.domains.collaboration.agents.definition import SafetyLimits
from allbrain.domains.collaboration.workflow.models import SubtaskResult
from allbrain.security._prompt_rules import PROMPT_INJECTION_PATTERNS


class SafetyError(Exception):
    """Raised when a safety check fails before/during/after execution."""


class CostCeilingExceeded(SafetyError):  # noqa: N818
    """Raised when the cost ceiling is exceeded."""


class RateLimitExceeded(SafetyError):  # noqa: N818
    """Raised when rate limit is hit."""


class InputRejected(SafetyError):  # noqa: N818
    """Raised when input fails sanitization."""


@dataclass
class SafetyState:
    workflow_cost: float = 0.0
    call_timestamps: deque[float] = field(default_factory=deque)


def sanitize_input(text: str) -> str:
    """Remove suspicious patterns that could be prompt injection attempts."""
    cleaned = text
    for pattern in PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def sanitize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a task dict recursively."""
    out: dict[str, Any] = {}
    for key, value in task.items():
        if isinstance(value, str):
            out[key] = sanitize_input(value)
        elif isinstance(value, dict):
            out[key] = sanitize_task(value)
        elif isinstance(value, list):
            out[key] = [sanitize_input(v) if isinstance(v, str) else v for v in value]
        else:
            out[key] = value
    return out


def estimate_input_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return max(1, len(text) // 4)


class SafetyWrapper:
    """Wraps an AgentAdapter with safety checks: sanitization, cost ceiling, rate limiting."""

    def __init__(
        self,
        adapter: AgentAdapter,
        limits: SafetyLimits | None = None,
        state: SafetyState | None = None,
    ) -> None:
        self.adapter = adapter
        self.limits = limits or adapter.definition.safety_limits
        self.state = state or SafetyState()

    def execute(
        self,
        *,
        task: dict[str, Any],
        context: ExecutionContext,
    ) -> SubtaskResult:
        # 1. Check domain allowlist
        domain = task.get("domain") or "software"
        if self.limits.allowed_domains and domain not in self.limits.allowed_domains:
            raise InputRejected(f"Domain '{domain}' not in allowed list")

        # 2. Sanitize input
        clean_task = sanitize_task(task)
        goal = str(clean_task.get("goal") or "")
        input_tokens = estimate_input_tokens(goal)
        if input_tokens > self.limits.max_input_tokens:
            raise InputRejected(f"Input tokens ({input_tokens}) exceed limit ({self.limits.max_input_tokens})")

        # 3. Cost ceiling check (per call + per workflow)
        estimated = self.adapter.estimate_cost(clean_task)
        if estimated > self.limits.max_cost_per_call:
            raise CostCeilingExceeded(
                f"Per-call cost {estimated:.4f} exceeds limit {self.limits.max_cost_per_call:.4f}"
            )
        if self.state.workflow_cost + estimated > self.limits.max_cost_per_workflow:
            raise CostCeilingExceeded(
                f"Workflow cost would exceed ceiling "
                f"({self.state.workflow_cost + estimated:.4f} > {self.limits.max_cost_per_workflow:.4f})"
            )

        # 4. Rate limit check
        self._check_rate_limit()

        # 5. Execute
        result = self.adapter.execute(task=clean_task, context=context)

        # 6. Track cost
        cost = result.metadata.get("cost_usd", estimated) if result.metadata else estimated
        self.state.workflow_cost += float(cost)
        self.state.call_timestamps.append(time.time())

        # 7. Validate output
        if len(result.output or "") > self.limits.max_output_tokens * 4:
            # rough chars-per-token check
            raise SafetyError("Output exceeds max_output_tokens limit")

        return result

    def _check_rate_limit(self) -> None:
        now = time.time()
        window = 60.0
        while self.state.call_timestamps and now - self.state.call_timestamps[0] > window:
            self.state.call_timestamps.popleft()
        if len(self.state.call_timestamps) >= self.limits.max_calls_per_minute:
            raise RateLimitExceeded(f"Rate limit exceeded: {len(self.state.call_timestamps)} calls in last {window}s")
