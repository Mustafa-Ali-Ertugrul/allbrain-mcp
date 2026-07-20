from __future__ import annotations

from allbrain.domains.reasoning.uncertainty.models import (
    ConfidenceComponent,
    KnowledgeGap,
    UncertaintyEstimate,
    UncertaintyType,
)

WEIGHTS = {
    "historical": 0.35,
    "evidence": 0.25,
    "consistency": 0.20,
    "samples": 0.20,
}


def composite_uncertainty(
    variance: float,
    evidence_count: int,
    contradiction_count: int,
) -> float:
    """Sprint 45: deterministic uncertainty composite for revision.

    new = variance + contradiction_count / evidence_count, clamped to [0, 1].

    Spec example: variance=0.20, evidence=20, contradictions=2 -> 0.20 + 0.10 = 0.30.
    (Spec narrative showed 0.31; the actual formula gives 0.30, with the example
    value being approximate. Documented in the Sprint 45 plan.)

    If evidence_count is 0, returns variance unchanged (no contradiction
    pressure can be computed without any evidence).
    """
    if evidence_count <= 0:
        return max(0.0, min(1.0, float(variance)))
    raw = float(variance) + float(contradiction_count) / float(evidence_count)
    return max(0.0, min(1.0, raw))


def _agreement_score(layer_indicators: list[float]) -> float:
    if not layer_indicators:
        return 0.0
    mean = sum(layer_indicators) / len(layer_indicators)
    variance = sum((x - mean) ** 2 for x in layer_indicators) / len(layer_indicators)
    return max(0.0, 1.0 - variance)


def estimate(
    *,
    historical: float,
    evidence: float,
    consistency_inputs: list[float],
    sample_count: int,
    sample_quality: float,
    gaps: list[KnowledgeGap] | None = None,
    analysis_id: str | None = None,
    historical_override: float | None = None,
    belief: object | None = None,
) -> UncertaintyEstimate:
    if historical_override is not None:
        historical = historical_override
    elif belief is not None:
        belief_mean = getattr(belief, "mean", None)
        if belief_mean is None and isinstance(belief, dict):
            belief_mean = belief.get("mean")
        if isinstance(belief_mean, (int, float)):
            historical = float(belief_mean)
    components = [
        ConfidenceComponent(name="historical", score=round(historical, 6)),
        ConfidenceComponent(name="evidence", score=round(evidence, 6)),
        ConfidenceComponent(name="consistency", score=round(_agreement_score(consistency_inputs), 6)),
        ConfidenceComponent(name="samples", score=round(sample_quality, 6)),
    ]
    confidence = round(
        sum(c.score * WEIGHTS[c.name] for c in components),
        6,
    )
    uncertainty = round(1.0 - confidence, 6)
    uncertainty_type = _classify(sample_count, confidence, consistency_inputs)
    return UncertaintyEstimate(
        confidence=confidence,
        uncertainty=uncertainty,
        uncertainty_type=uncertainty_type,
        components=components,
        knowledge_gaps=gaps or [],
        analysis_id=analysis_id,
    )


def _classify(sample_count: int, confidence: float, consistency_inputs: list[float]) -> UncertaintyType:
    if sample_count < 5:
        return UncertaintyType.EPISTEMIC
    if not consistency_inputs:
        return UncertaintyType.ALEATORIC
    if confidence >= 0.7 and _agreement_score(consistency_inputs) >= 0.8:
        return UncertaintyType.ALEATORIC
    return UncertaintyType.MIXED
