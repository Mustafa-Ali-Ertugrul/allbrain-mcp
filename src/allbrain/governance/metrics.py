from __future__ import annotations

from collections import Counter
from typing import Any

from allbrain.models.schemas import EventRead


class GovernanceMetrics:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        decisions: list[dict[str, Any]] = []
        alignment_scores: list[float] = []
        trajectory_scores: list[float] = []
        identity_scores: list[float] = []
        constitutional_violations = 0
        autonomy_levels: list[int] = []

        for event in events:
            payload = event.payload
            if event.type == "governance_decision_synthesized":
                decisions.append(payload)
                if isinstance(payload.get("alignment_score"), int | float):
                    alignment_scores.append(float(payload["alignment_score"]))
                if isinstance(payload.get("trajectory_score"), int | float):
                    trajectory_scores.append(float(payload["trajectory_score"]))
                if isinstance(payload.get("autonomy_level_allowed"), int):
                    autonomy_levels.append(int(payload["autonomy_level_allowed"]))
            elif event.type == "governance_alignment_evaluated":
                if isinstance(payload.get("alignment_score"), int | float):
                    alignment_scores.append(float(payload["alignment_score"]))
                if isinstance(payload.get("identity_consistency_score"), int | float):
                    identity_scores.append(float(payload["identity_consistency_score"]))
                constitutional_violations += len(payload.get("constitutional_violations", []) or [])
            elif event.type == "governance_post_check_completed":
                if payload.get("constitutional_violation"):
                    constitutional_violations += 1

        counts = Counter(str(item.get("decision")) for item in decisions)
        total = max(1, len(decisions))
        return {
            "alignment_drift_rate": round(1.0 - _average(alignment_scores, 1.0), 6),
            "trajectory_deviation_index": round(1.0 - _average(trajectory_scores, 1.0), 6),
            "autonomy_expansion_velocity": _velocity(autonomy_levels),
            "rejected_mutation_ratio": round(counts["reject_expansion"] / total, 6),
            "constrained_mutation_ratio": round(
                (counts["approve_with_constraints"] + counts["partial_approval"]) / total, 6
            ),
            "constitutional_violation_frequency": constitutional_violations,
            "system_identity_stability_score": _average(identity_scores, 1.0),
            "decision_counts": dict(sorted(counts.items())),
        }


def _average(values: list[float], default: float) -> float:
    return round(sum(values) / len(values), 6) if values else default


def _velocity(levels: list[int]) -> float:
    if len(levels) < 2:
        return 0.0
    return round((levels[-1] - levels[0]) / (len(levels) - 1), 6)
