from __future__ import annotations

from allbrain.decision.model import DecisionContext
from allbrain.routing import (
    causal_selection_score,
    dynamics_selection_score,
    selection_score,
    unified_decision_score,
)


def fusion_backend(ctx: DecisionContext) -> tuple[float, dict[str, float]]:
    sv = ctx.fusion or {}
    chs = {"capability", "learning", "dynamics", "causal"}
    contribs = {ch: float(sv.get(ch, 0.0)) for ch in chs}
    score = unified_decision_score(
        capability=contribs["capability"],
        learning=contribs["learning"],
        dynamics=contribs["dynamics"],
        causal=contribs["causal"],
        capability_weight=float(sv.get("weight_capability", 0.25)),
        learning_weight=float(sv.get("weight_learning", 0.25)),
        dynamics_weight=float(sv.get("weight_dynamics", 0.25)),
        causal_weight=float(sv.get("weight_causal", 0.25)),
    )
    return score, contribs


def causal_backend(ctx: DecisionContext) -> tuple[float, dict[str, float]]:
    cap = ctx.capability
    learn = ctx.learning
    dyn = ctx.dynamics
    caus = ctx.causal
    tel = ctx.telemetry
    score = causal_selection_score(
        reputation=float(tel.get("reputation", 0.5)),
        runtime_score=float(tel.get("runtime_score", 0.5)),
        calibrated_trust=float(learn.get("calibrated_trust", 0.5)),
        consensus_score=float(learn.get("consensus_score", 0.5)),
        capability_match=float(cap.get("match_score", 0.0)),
        learned_capability=float(learn.get("capability_score", 0.0)),
        drift_score=float(dyn.get("drift_score", 0.0)),
        trend_label=str(dyn.get("trend_label", "stable")),
        forecast_score=float(dyn.get("forecast_score", 0.0)),
        impact_score=float(caus.get("impact_score", 0.0)),
        causal_confidence=float(caus.get("confidence", 0.0)),
    )
    contribs = {
        "impact_score": float(caus.get("impact_score", 0.0)),
        "causal_confidence": float(caus.get("confidence", 0.0)),
    }
    return score, contribs


def dynamics_backend(ctx: DecisionContext) -> tuple[float, dict[str, float]]:
    cap = ctx.capability
    learn = ctx.learning
    dyn = ctx.dynamics
    tel = ctx.telemetry
    score = dynamics_selection_score(
        reputation=float(tel.get("reputation", 0.5)),
        runtime_score=float(tel.get("runtime_score", 0.5)),
        calibrated_trust=float(learn.get("calibrated_trust", 0.5)),
        consensus_score=float(learn.get("consensus_score", 0.5)),
        capability_match=float(cap.get("match_score", 0.0)),
        learned_capability=float(learn.get("capability_score", 0.0)),
        drift_score=float(dyn.get("drift_score", 0.0)),
        trend_label=str(dyn.get("trend_label", "stable")),
        forecast_score=float(dyn.get("forecast_score", 0.0)),
    )
    contribs = {"drift_score": float(dyn.get("drift_score", 0.0))}
    return score, contribs


def legacy_backend(ctx: DecisionContext) -> tuple[float, dict[str, float]]:
    learn = ctx.learning
    tel = ctx.telemetry
    score = selection_score(
        reputation=float(tel.get("reputation", 0.5)),
        runtime_score=float(tel.get("runtime_score", 0.5)),
        calibrated_trust=float(learn.get("calibrated_trust", 0.5)),
        consensus_score=float(learn.get("consensus_score", 0.5)),
    )
    return score, {"legacy": 1.0}
