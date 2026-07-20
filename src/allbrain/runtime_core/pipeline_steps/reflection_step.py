from __future__ import annotations

from typing import Any

from allbrain.domains.reasoning.foresight.models import ForesightAnalysis, FuturePlan
from allbrain.domains.reasoning.information_seeking import INFORMATION_SEEKING_TEMPLATE_VERSION
from allbrain.domains.reasoning.meta_reasoning import META_REASONING_TEMPLATE_VERSION
from allbrain.domains.reasoning.uncertainty import UNCERTAINTY_TEMPLATE_VERSION
from allbrain.domains.reasoning.uncertainty.models import KnowledgeGap
from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.runtime_core.observability import ObservabilityCollector
from allbrain.runtime_core.pipeline_models import PipelineRunState
from allbrain.runtime_core.pipeline_services import PipelineServices


class ReflectionStep:
    """Run optional meta-reasoning, uncertainty, and information-seeking stages."""

    def execute(self, state: PipelineRunState, services: PipelineServices) -> None:
        options = state.options
        if options.enable_meta_reasoning and state.foresight is not None:
            state.meta_reasoning, state.last_event_id, events = self._meta_reasoning(state, services)
            state.emitted.extend(events)
        if options.enable_uncertainty and state.meta_reasoning is not None:
            state.uncertainty, state.last_event_id, events = self._uncertainty(state, services)
            state.emitted.extend(events)
        if options.enable_information_seeking and state.uncertainty is not None:
            gaps = state.uncertainty.get("uncertainty", {}).get("knowledge_gaps", [])
            if gaps:
                state.information_seeking, state.last_event_id, events = self._information_seeking(
                    state, services, gaps
                )
                state.emitted.extend(events)

    @staticmethod
    def _meta_reasoning(
        state: PipelineRunState, services: PipelineServices
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        payload = state.foresight or {}
        best_payload = payload["best_plan"]
        best = FuturePlan.model_validate(best_payload)
        candidates = [FuturePlan.model_validate(item) for item in payload.get("plans", []) if item is not best_payload]
        analysis_id = payload.get("analysis_id") or str(services.uuid7_generator())
        analysis = ForesightAnalysis(
            analysis_id=services.uuid7_generator(),
            action=payload.get("action", "unknown"),
            best_plan=best,
            expected_plan=best,
            safest_plan=best,
            fastest_plan=best,
            plan_spread=0.0,
            strategy_uncertainty=0.0,
            horizon_risk=best.cumulative_risk,
            plans=[best, *candidates],
        )
        started = state.bus.publish(
            type=EventType.META_REASONING_STARTED.value,
            payload={
                "action": payload.get("action", "unknown"),
                "foresight_analysis_id": str(analysis_id),
                "template_version": META_REASONING_TEMPLATE_VERSION,
            },
            caused_by=state.last_event_id,
        )
        explanation = services.meta_reasoning.explain(best, candidates, analysis)
        explained_payload = explanation.model_dump(mode="json")
        explained_payload["foresight_analysis_id"] = str(analysis_id)
        explained = state.bus.publish(
            type=EventType.DECISION_EXPLAINED.value,
            payload=explained_payload,
            caused_by=started.id,
            impact_score=explanation.confidence.confidence,
        )
        completed = state.bus.publish(
            type=EventType.META_REASONING_COMPLETED.value,
            payload={
                "foresight_analysis_id": str(analysis_id),
                "summary": {
                    "selected": explanation.selected_option,
                    "confidence": explanation.confidence.confidence,
                    "rejected_count": len(explanation.rejected),
                },
                "template_version": META_REASONING_TEMPLATE_VERSION,
            },
            caused_by=explained.id,
        )
        summary = {
            "selected_option": explanation.selected_option,
            "confidence": explanation.confidence.model_dump(mode="json"),
            "reasons": [item.model_dump(mode="json") for item in explanation.reasons],
            "rejected": [item.model_dump(mode="json") for item in explanation.rejected],
            "template_version": META_REASONING_TEMPLATE_VERSION,
            "foresight_analysis_id": str(analysis_id),
        }
        return summary, completed.id, [started, explained, completed]

    @staticmethod
    def _uncertainty(
        state: PipelineRunState, services: PipelineServices
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        meta = state.meta_reasoning or {}
        indicators = ObservabilityCollector.collect_layer_indicators(
            state.world_payload,
            state.counterfactual,
            state.scenarios,
            state.foresight,
            meta,
        )
        sample_count = len(state.foresight.get("plans", [])) if state.foresight else 0
        quality = state.foresight["best_plan"].get("confidence", 0.0) if state.foresight else 0.0
        historical = ObservabilityCollector.collect_historical_rate(
            state.context, state.options.project_path, objective=state.objective
        )
        evidence = sum(indicators) / len(indicators) if indicators else 0.0
        analysis_id = str(meta.get("foresight_analysis_id") or "")
        estimate = services.uncertainty.analyze(
            historical=historical,
            evidence=evidence,
            layer_indicators=indicators,
            sample_count=sample_count,
            sample_quality=quality,
            has_feedback=True,
            analysis_id=analysis_id,
            belief=None,
        )
        estimated = state.bus.publish(
            type=EventType.UNCERTAINTY_ESTIMATED.value,
            payload=estimate.model_dump(mode="json"),
            caused_by=state.last_event_id,
            impact_score=estimate.uncertainty,
        )
        gap_event = None
        if estimate.knowledge_gaps:
            gap_event = state.bus.publish(
                type=EventType.KNOWLEDGE_GAP_DETECTED.value,
                payload={
                    "analysis_id": analysis_id,
                    "topics": [gap.topic for gap in estimate.knowledge_gaps],
                    "gaps": [gap.model_dump(mode="json") for gap in estimate.knowledge_gaps],
                    "template_version": UNCERTAINTY_TEMPLATE_VERSION,
                },
                caused_by=estimated.id,
            )
        calibrated = state.bus.publish(
            type=EventType.CONFIDENCE_CALIBRATED.value,
            payload={
                "analysis_id": analysis_id,
                "raw_confidence": estimate.confidence,
                "observed_rate": historical,
                "calibrated_confidence": estimate.confidence,
                "template_version": UNCERTAINTY_TEMPLATE_VERSION,
            },
            caused_by=gap_event.id if gap_event is not None else estimated.id,
        )
        summary = {
            "action": meta.get("selected_option", "unknown"),
            "analysis_id": analysis_id,
            "uncertainty": estimate.model_dump(mode="json"),
            "gaps": [gap.model_dump(mode="json") for gap in estimate.knowledge_gaps],
            "calibrated_confidence": estimate.confidence,
            "template_version": UNCERTAINTY_TEMPLATE_VERSION,
        }
        events = [estimated, *([gap_event] if gap_event is not None else []), calibrated]
        return summary, calibrated.id, events

    @staticmethod
    def _information_seeking(
        state: PipelineRunState, services: PipelineServices, gaps_payload: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], str, list[EventRead]]:
        uncertainty = state.uncertainty or {}
        analysis_id = str(uncertainty.get("analysis_id") or "")
        gaps = [KnowledgeGap.model_validate(item) for item in gaps_payload]
        plan = services.information_seeking.analyze(gaps, analysis_id=analysis_id or None)
        events: list[EventRead] = []
        caused_by = state.last_event_id
        last_need_id = caused_by
        for need in plan.needs:
            event = state.bus.publish(
                type=EventType.INFORMATION_NEED_DETECTED.value,
                payload={
                    "analysis_id": str(plan.analysis_id),
                    "topic": need.topic,
                    "expected_gain": need.expected_gain,
                    "cost": need.cost,
                    "priority": need.priority,
                    "template_version": INFORMATION_SEEKING_TEMPLATE_VERSION,
                },
                caused_by=caused_by,
                impact_score=need.priority,
            )
            events.append(event)
            last_need_id = event.id
        caused_by = last_need_id
        if plan.selected_action is not None:
            gain = state.bus.publish(
                type=EventType.INFORMATION_GAIN_ESTIMATED.value,
                payload={
                    "analysis_id": str(plan.analysis_id),
                    "action": plan.selected_action.value,
                    "expected_voi": plan.expected_voi,
                    "rationale": (
                        f"selected {plan.selected_action.value} with VOI {plan.expected_voi} "
                        f"for {len(plan.needs)} need(s)"
                    ),
                    "template_version": INFORMATION_SEEKING_TEMPLATE_VERSION,
                },
                caused_by=caused_by,
                impact_score=plan.expected_voi,
            )
            events.append(gain)
            caused_by = gain.id
        selected = state.bus.publish(
            type=EventType.INFORMATION_ACTION_SELECTED.value,
            payload=plan.model_dump(mode="json"),
            caused_by=caused_by,
        )
        events.append(selected)
        summary = {
            "analysis_id": str(plan.analysis_id),
            "needs": [item.model_dump(mode="json") for item in plan.needs],
            "selected_action": plan.selected_action.value if plan.selected_action else None,
            "expected_voi": plan.expected_voi,
            "rationale": plan.rationale,
            "template_version": INFORMATION_SEEKING_TEMPLATE_VERSION,
        }
        return summary, selected.id, events

