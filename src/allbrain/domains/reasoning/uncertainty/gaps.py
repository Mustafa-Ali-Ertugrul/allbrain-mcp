from __future__ import annotations

from allbrain.domains.reasoning.uncertainty.models import KnowledgeGap

MIN_SAMPLES_THRESHOLD = 5
HIGH_SEVERITY = 0.7
MEDIUM_SEVERITY = 0.4


def detect(
    *,
    sample_count: int,
    historical: float | None,
    layer_indicators: list[float] | None = None,
    has_feedback: bool = True,
) -> list[KnowledgeGap]:
    gaps: list[KnowledgeGap] = []

    if sample_count < MIN_SAMPLES_THRESHOLD:
        severity = HIGH_SEVERITY if sample_count == 0 else MEDIUM_SEVERITY
        gaps.append(
            KnowledgeGap(
                topic="insufficient_samples",
                severity=severity,
                description=f"Only {sample_count} sample(s) available; need >= {MIN_SAMPLES_THRESHOLD}",
                recoverable=True,
            )
        )

    if historical is None:
        gaps.append(
            KnowledgeGap(
                topic="missing_history",
                severity=HIGH_SEVERITY,
                description="No historical decision data available for this context",
                recoverable=True,
            )
        )

    if layer_indicators is not None and len(layer_indicators) >= 2:
        mean = sum(layer_indicators) / len(layer_indicators)
        max_dev = max(abs(x - mean) for x in layer_indicators)
        if max_dev > 0.2:
            gaps.append(
                KnowledgeGap(
                    topic="inconsistent_world_model",
                    severity=min(1.0, max_dev),
                    description=f"Reasoning layers disagree by {round(max_dev, 3)} on this decision",
                    recoverable=True,
                )
            )

    if not has_feedback:
        gaps.append(
            KnowledgeGap(
                topic="missing_feedback",
                severity=MEDIUM_SEVERITY,
                description="No execution feedback recorded yet for this decision",
                recoverable=True,
            )
        )

    return gaps

