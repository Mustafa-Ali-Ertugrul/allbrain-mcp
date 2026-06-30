from __future__ import annotations

from allbrain.decision.model import DecisionContext, DecisionResult


def build_minimal_trace(result: DecisionResult) -> dict[str, float]:
    """AUTO/FUSION/CAUSAL/DYNAMIC/LEGACY mode: minimal trace."""
    return {
        "final_score": result.score,
        "contributors": result.contributors,
    }


def build_debug_trace(result: DecisionResult, ctx: DecisionContext) -> dict:
    """DEBUG mode: full breakdown with per-backend comparison."""
    return {
        "final_score": result.score,
        "mode": result.mode,
        "contributors": result.contributors,
        "backend_trace": list(result.backend_trace),
        "context_summary": {
            "capability_keys": sorted(ctx.capability.keys()),
            "learning_keys": sorted(ctx.learning.keys()),
            "dynamics_keys": sorted(ctx.dynamics.keys()),
            "causal_keys": sorted(ctx.causal.keys()),
            "fusion_active": ctx.fusion is not None,
        },
    }
