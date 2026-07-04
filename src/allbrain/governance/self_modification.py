from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from uuid6 import uuid7


class SelfModificationGuard:
    """Tracks self-modification rejection history and detects repetitive rejection patterns.

    The guard prevents the system from entering a rejection loop where the same
    proposals are repeatedly submitted and rejected without meaningful change.

    Attributes:
        window_seconds: Time window in seconds for counting rejections.
        threshold: Number of rejections within window that triggers escalation.
    """

    def __init__(self, window_seconds: int = 300, threshold: int = 3) -> None:
        self._window_seconds = window_seconds
        self._threshold = threshold
        self._history: dict[str, list[tuple[str, datetime]]] = {}

    def record_rejection(self, agent_id: str, reason: str, timestamp: datetime | None = None) -> None:
        """Record a rejection event for an agent.

        Args:
            agent_id: Identifier for the agent or proposal batch.
            reason: Rejection reason (e.g., 'alignment_or_constitutional_boundary_failed').
            timestamp: When the rejection occurred (defaults to now).
        """
        ts = timestamp or datetime.now(UTC)
        self._history.setdefault(agent_id, []).append((reason, ts))
        self._prune(agent_id)

    def detect_repetitive_rejection(
        self,
        agent_id: str,
        window_seconds: int | None = None,
        threshold: int | None = None,
    ) -> bool:
        """Check if agent has been rejected too many times in the window.

        Args:
            agent_id: Agent identifier to check.
            window_seconds: Override default window (default uses instance value).
            threshold: Override default threshold (default uses instance value).

        Returns:
            True if rejections exceed threshold, False otherwise.
        """
        window = window_seconds if window_seconds is not None else self._window_seconds
        limit = threshold if threshold is not None else self._threshold
        now = datetime.now(UTC)
        cutoff = now.timestamp() - window
        count = sum(1 for _, ts in self._history.get(agent_id, []) if ts.timestamp() > cutoff)
        return count >= limit

    def can_propose(self, agent_id: str) -> tuple[bool, str]:
        """Check if an agent can submit new proposals without supervisor escalation.

        Args:
            agent_id: Agent identifier to check.

        Returns:
            Tuple of (can_propose: bool, reason: str).
        """
        if self.detect_repetitive_rejection(agent_id):
            window = self._window_seconds
            limit = self._threshold
            return (
                False,
                f"agent {agent_id} rejected {limit}+ times in last {window}s — supervisor escalation required",
            )
        return True, "ok"

    def clear_history(self, agent_id: str) -> None:
        """Clear rejection history for an agent.

        Args:
            agent_id: Agent to reset.
        """
        self._history.pop(agent_id, None)

    def get_rejection_summary(self, agent_id: str) -> dict[str, Any]:
        """Return rejection stats for diagnostics.

        Args:
            agent_id: Agent to inspect.

        Returns:
            Dict with total_rejections, recent_rejections, reasons, and can_propose.
        """
        entries = self._history.get(agent_id, [])
        now = datetime.now(UTC)
        cutoff = now.timestamp() - self._window_seconds
        recent = [e for e in entries if e[1].timestamp() > cutoff]
        reasons: dict[str, int] = {}
        for reason, _ in recent:
            reasons[reason] = reasons.get(reason, 0) + 1
        can, msg = self.can_propose(agent_id)
        return {
            "agent_id": agent_id,
            "total_rejections": len(entries),
            "recent_rejections": len(recent),
            "window_seconds": self._window_seconds,
            "threshold": self._threshold,
            "reasons": reasons,
            "can_propose": can,
            "message": msg,
        }

    def _prune(self, agent_id: str) -> None:
        """Remove entries outside the window."""
        cutoff = datetime.now(UTC).timestamp() - self._window_seconds
        entries = self._history.get(agent_id, [])
        self._history[agent_id] = [(r, ts) for r, ts in entries if ts.timestamp() > cutoff]


class SelfModificationAuthorityEngine:
    REJECT_ALIGNMENT = 0.45
    REJECT_TRAJECTORY = 0.35
    REJECT_SAFETY = 0.40
    RESTRUCTURE_IDENTITY = 0.50
    DELAY_CONFIDENCE = 0.50
    APPROVE_SCORE = 0.75
    APPROVE_CONFIDENCE = 0.70

    def decide(
        self,
        *,
        proposals: list[dict[str, Any]],
        alignment_report: dict[str, Any],
        trajectory: dict[str, Any],
        identity: dict[str, Any],
        autonomy_assessment: dict[str, Any],
        constitutional: dict[str, Any],
    ) -> dict[str, Any]:
        risk_level = _risk_level(proposals)
        confidence = min(float(trajectory["confidence"]), _proposal_confidence(proposals))
        has_architecture_mutation = any(proposal.get("change_type") == "architecture_change" for proposal in proposals)
        weakens_auditability = any(
            proposal.get("removes_auditability") or proposal.get("reduces_interpretability") for proposal in proposals
        )

        if (
            constitutional["has_explicit_violation"]
            or alignment_report["alignment_score"] < self.REJECT_ALIGNMENT
            or trajectory["trajectory_score"] < self.REJECT_TRAJECTORY
            or alignment_report["safety_alignment_score"] < self.REJECT_SAFETY
        ):
            decision = "reject_expansion"
            reason = "alignment_or_constitutional_boundary_failed"
        elif identity["identity_consistency_score"] < self.RESTRUCTURE_IDENTITY or (
            has_architecture_mutation and weakens_auditability
        ):
            decision = "require_restructuring"
            reason = "identity_or_auditability_requires_restructure"
        elif confidence < self.DELAY_CONFIDENCE or trajectory["confidence"] < self.DELAY_CONFIDENCE:
            decision = "delay_expansion"
            reason = "insufficient_governance_confidence"
        elif autonomy_assessment["requires_escalation"]:
            decision = "escalate_to_supervision"
            reason = "autonomy_transition_exceeds_governance_band"
        elif (
            risk_level == "high"
            or autonomy_assessment["autonomy_impact"] > 1
            or trajectory["trajectory_score"] < self.APPROVE_SCORE
            or alignment_report["alignment_score"] < self.APPROVE_SCORE
            or any(proposal.get("reduces_interpretability") for proposal in proposals)
        ):
            decision = "approve_with_constraints"
            reason = "constrain_first_governance"
        else:
            decision = "approve_expansion"
            reason = "alignment_and_trajectory_within_governance_bounds"

        return {
            "decision_id": str(uuid7()),
            "proposal_id": _first_proposal_id(proposals),
            "decision": decision,
            "risk_level": risk_level,
            "confidence": round(confidence, 6),
            "reasoning": reason,
            "rollback_conditions": [
                "alignment_score_degrades",
                "trajectory_score_degrades",
                "constitutional_violation_detected",
            ],
        }


def _risk_level(proposals: list[dict[str, Any]]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    selected = "low"
    for proposal in proposals:
        risk = str(proposal.get("risk_level", "low"))
        if order.get(risk, 0) > order[selected]:
            selected = "high" if risk == "critical" else risk
    return selected


def _proposal_confidence(proposals: list[dict[str, Any]]) -> float:
    values = [float(proposal.get("confidence", 0.75)) for proposal in proposals]
    return min(values) if values else 0.75


def _first_proposal_id(proposals: list[dict[str, Any]]) -> str | None:
    for proposal in proposals:
        if isinstance(proposal.get("proposal_id"), str):
            return proposal["proposal_id"]
    return None
