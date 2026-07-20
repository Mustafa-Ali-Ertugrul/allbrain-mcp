from __future__ import annotations

import hashlib

from allbrain.domains.reasoning.decision.backends import (
    causal_backend,
    dynamics_backend,
    fusion_backend,
    legacy_backend,
)
from allbrain.domains.reasoning.decision.model import DecisionContext, DecisionMode, DecisionResult
from allbrain.domains.reasoning.decision.resolver import resolve_mode


class DecisionEngine:
    def decide(
        self,
        ctx: DecisionContext,
        *,
        strict: bool = True,
        workspace_items: tuple | None = None,
        episodes: tuple | None = None,
        concepts: tuple | None = None,
    ) -> DecisionResult:
        """Single entry point for all decision types.

        strict=True (production): unknown fields â†’ ValueError.
        strict=False (debug/testing): tolerant mode, unknown fields ignored.

        DEBUG mode (Refinement #3): read-only dry-run.
        No events emitted, no reducers mutated.

        Sprint 61: workspace_items added as informational (backward compat).
        Sprint 62: episodes added as informational (backward compat).
        Sprint 63: concepts added as informational (backward compat).
        """
        if strict:
            self._validate_context(ctx)

        mode = resolve_mode(ctx)

        if mode == DecisionMode.DEBUG:
            return self._run_debug(ctx, episodes=episodes, concepts=concepts)

        backend_map = {
            DecisionMode.FUSION: fusion_backend,
            DecisionMode.CAUSAL: causal_backend,
            DecisionMode.DYNAMIC: dynamics_backend,
            DecisionMode.LEGACY: legacy_backend,
        }
        backend = backend_map.get(mode)
        if backend is None:
            backend = legacy_backend
            mode = DecisionMode.LEGACY

        score, contribs = backend(ctx)

        analysis_id = _stable_decision_id(ctx.agent_id, ctx.task_type, str(mode), score)

        return DecisionResult(
            agent_id=ctx.agent_id,
            task_type=ctx.task_type,
            score=score,
            mode=str(mode),
            contributors=contribs,
            backend_trace=(str(mode), "calibrated", "weighted", "clamped"),
            workspace_items=workspace_items,
            episodes=episodes,
            concepts=concepts,
            analysis_id=analysis_id,
        )

    def _run_debug(
        self, ctx: DecisionContext, *, episodes: tuple | None = None, concepts: tuple | None = None
    ) -> DecisionResult:
        """DEBUG mode: full trace with all 4 backends compared.

        Refinement #3: read-only dry-run. No events emitted.
        """
        results: dict[str, tuple[float, dict[str, float]]] = {}
        backends = [
            ("fusion", fusion_backend),
            ("causal", causal_backend),
            ("dynamics", dynamics_backend),
            ("legacy", legacy_backend),
        ]
        for name, fn in backends:
            score, contribs = fn(ctx)
            results[name] = (score, contribs)

        primary_score, primary_contribs = results.get("fusion", results.get("legacy", (0.0, {})))
        merged_contribs: dict[str, float] = {}
        for name, (score, contribs) in results.items():
            for k, v in contribs.items():
                merged_contribs[f"{name}.{k}"] = v
            merged_contribs[f"{name}.score"] = score

        trace_path = tuple(f"{name}->{score:.3f}" for name, (score, _) in results.items())

        analysis_id = _stable_decision_id(ctx.agent_id, ctx.task_type, "debug", primary_score)

        return DecisionResult(
            agent_id=ctx.agent_id,
            task_type=ctx.task_type,
            score=primary_score,
            mode="debug",
            contributors=merged_contribs,
            backend_trace=trace_path,
            episodes=episodes,
            concepts=concepts,
            analysis_id=analysis_id,
        )

    @staticmethod
    def _validate_context(ctx: DecisionContext) -> None:
        if not ctx.agent_id or not ctx.task_type:
            raise ValueError("DecisionContext must have agent_id and task_type")


def _stable_decision_id(agent_id: str, task_type: str, mode: str, score: float) -> str:
    d = hashlib.sha256(f"{agent_id}:{task_type}:{mode}:{score:.6f}".encode()).digest()
    return f"dec-{d.hex()[:12]}"

