"""Learning and adaptation orchestration extracted from SystemDecisionPipeline."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.runtime_core.contracts import RuntimeContext
from allbrain.runtime_core.event_bus import RuntimeEventBus

if TYPE_CHECKING:
    from allbrain.runtime_core.learning import ClosedLoopLearningEngine
    from allbrain.runtime_core.memory import GlobalExperienceMemoryBuilder

logger = logging.getLogger(__name__)


class LearningOrchestrator:
    """Orchestrates learning, causal analysis, dynamics modeling, and fusion."""

    def __init__(
        self,
        learning: ClosedLoopLearningEngine,
        memory: GlobalExperienceMemoryBuilder,
        uuid7_generator: Any,
    ) -> None:
        self.learning = learning
        self.memory = memory
        self._uuid7 = uuid7_generator

    def learning_step(
        self,
        bus: RuntimeEventBus,
        context: RuntimeContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit AGENT_CAPABILITY_OBSERVED + AGENT_CAPABILITY_LEARNED/DECAYED events."""
        from allbrain.capabilities import CapabilityManager
        from allbrain.learning import CapabilityLearningManager, make_observed_payload

        learning_mgr = CapabilityLearningManager()

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by
        task_type = (
            str(scheduler_result.get("assignment", {}).get("agent_id", "implementation"))
            if scheduler_result
            else "implementation"
        )

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for learning step: %s", exc, exc_info=True)
            events = []

        cap_mgr = CapabilityManager()
        agent_ids = cap_mgr.known_keys(events)
        if not agent_ids:
            return None, caused_by, []

        observed = bus.publish(
            type=EventType.AGENT_CAPABILITY_OBSERVED.value,
            payload=make_observed_payload(
                agent_id="system", task_type=task_type, success=True, runtime_score=0.0, selection_score=0.0
            ),
            caused_by=caused_by,
        )

        learned_events = []
        for k in sorted(agent_ids):
            aid, tt = k.split("::", 1)
            old_state = learning_mgr.query(events, agent_id=aid, task_type=tt)
            old_score = old_state.capability_score

            obs = 0.5
            new_score = old_score * 0.9 + obs * 0.1
            new_score = max(0.0, min(1.0, new_score))
            delta = new_score - old_score

            if abs(delta) < 0.02:
                continue

            if delta < 0:
                le = bus.publish(
                    type=EventType.AGENT_CAPABILITY_DECAYED.value,
                    payload={"agent_id": aid, "task_type": tt, "old_score": old_score, "new_score": new_score},
                    caused_by=caused_by,
                )
                learned_events.append(le)
                continue

            le = bus.publish(
                type=EventType.AGENT_CAPABILITY_LEARNED.value,
                payload={
                    "agent_id": aid,
                    "task_type": tt,
                    "old_score": old_score,
                    "new_score": new_score,
                    "delta": delta,
                },
                caused_by=caused_by,
            )
            learned_events.append(le)

        summary = {"task_id": task_id, "task_type": task_type, "learned_agents": len(learned_events)}
        return summary, observed.id, [observed] + learned_events

    def causal_step(
        self,
        bus: RuntimeEventBus,
        context: RuntimeContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit AGENT_COUNTERFACTUAL_RUN + AGENT_CAUSAL_IMPACT_RECORDED events."""
        from allbrain.capabilities import CapabilityManager
        from allbrain.causal import CausalManager, make_counterfactual_payload, make_impact_payload
        from allbrain.causal.model import CAUSAL_IMPACT_THRESHOLD, CAUSAL_MIN_SAMPLES

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for causal step: %s", exc, exc_info=True)
            events = []

        cap_mgr = CapabilityManager()
        agent_ids = cap_mgr.known_keys(events)
        if not agent_ids:
            return None, caused_by, []

        causal_mgr = CausalManager()
        causal_events: list[EventRead] = []

        for k in sorted(agent_ids):
            aid, tt = k.split("::", 1)
            result = causal_mgr.query(events, agent_id=aid, task_type=tt)

            cf_data = result.get("counterfactuals", {})
            impacts = result.get("impacts", {})

            for alt, cf in cf_data.items():
                if cf.get("sample_count", 0) < CAUSAL_MIN_SAMPLES:
                    continue
                ce = bus.publish(
                    type=EventType.AGENT_COUNTERFACTUAL_RUN.value,
                    payload=make_counterfactual_payload(
                        agent_id=aid,
                        task_type=tt,
                        actual_agent=aid,
                        alternative_agent=alt,
                        actual_outcome=float(cf.get("actual_outcome", 0.0)),
                        alternative_outcome=float(cf.get("alternative_outcome", 0.0)),
                        impact_score=float(cf.get("impact_score", 0.0)),
                        confidence=float(cf.get("confidence", 0.0)),
                        sample_count=int(cf.get("sample_count", 0)),
                    ),
                    caused_by=caused_by,
                )
                causal_events.append(ce)

            for alt, imp in impacts.items():
                impact_score = float(imp.get("impact_score", 0.0))
                if abs(impact_score) < CAUSAL_IMPACT_THRESHOLD:
                    continue
                if imp.get("sample_count", 0) < CAUSAL_MIN_SAMPLES:
                    continue
                ie = bus.publish(
                    type=EventType.AGENT_CAUSAL_IMPACT_RECORDED.value,
                    payload=make_impact_payload(
                        agent_id=aid,
                        task_type=tt,
                        alternative_agent=alt,
                        impact_score=impact_score,
                        confidence=float(imp.get("confidence", 0.0)),
                        sample_count=int(imp.get("sample_count", 0)),
                    ),
                    caused_by=caused_by,
                )
                causal_events.append(ie)

        summary = {
            "task_id": task_id,
            "agent_count": len(agent_ids),
            "counterfactual_count": len(causal_events),
        }
        return summary, caused_by, causal_events

    def dynamics_step(
        self,
        bus: RuntimeEventBus,
        context: RuntimeContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit AGENT_CAPABILITY_DRIFT_DETECTED + TREND_UPDATED + FORECAST_UPDATED events."""
        from allbrain.capabilities import CapabilityManager
        from allbrain.dynamics import CapabilityDynamicsManager

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for dynamics step: %s", exc, exc_info=True)
            events = []

        cap_mgr = CapabilityManager()
        agent_ids = cap_mgr.known_keys(events)
        if not agent_ids:
            return None, caused_by, []

        dynamics_mgr = CapabilityDynamicsManager()
        dynamics_events: list[EventRead] = []

        for k in sorted(agent_ids):
            aid, tt = k.split("::", 1)
            result = dynamics_mgr.query(events, agent_id=aid, task_type=tt)
            dynamics_events.extend(self._publish_dynamics(bus, aid, tt, result, caused_by))

        summary = {
            "task_id": task_id,
            "agent_count": len(agent_ids),
            "drift_count": sum(
                1
                for e in dynamics_events
                if str(getattr(e, "type", "")) == EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value
            ),
            "trend_count": sum(
                1
                for e in dynamics_events
                if str(getattr(e, "type", "")) == EventType.AGENT_CAPABILITY_TREND_UPDATED.value
            ),
            "forecast_count": sum(
                1
                for e in dynamics_events
                if str(getattr(e, "type", "")) == EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value
            ),
        }
        return summary, caused_by, dynamics_events

    @staticmethod
    def _publish_dynamics(
        bus: RuntimeEventBus, aid: str, task_type: str, result: dict[str, Any], caused_by: str
    ) -> list[EventRead]:
        from allbrain.dynamics import make_drift_payload, make_forecast_payload, make_trend_payload
        from allbrain.dynamics.model import (
            DRIFT_THRESHOLD,
            FORECAST_DEFAULT_HORIZON,
            MIN_OBSERVATIONS_FOR_DRIFT,
            TREND_HYSTERESIS_COUNT,
        )

        published: list[EventRead] = []
        drift = result.get("drift", {})
        drift_score = float(drift.get("drift_score", 0.0))
        if drift_score >= DRIFT_THRESHOLD and int(drift.get("observation_count", 0)) >= MIN_OBSERVATIONS_FOR_DRIFT:
            published.append(
                bus.publish(
                    type=EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
                    payload=make_drift_payload(
                        agent_id=aid,
                        task_type=task_type,
                        drift_score=drift_score,
                        drift_level=str(drift.get("drift_level", "low")),
                        ema_short=float(drift.get("ema_short", 0.0)),
                        ema_long=float(drift.get("ema_long", 0.0)),
                    ),
                    caused_by=caused_by,
                )
            )
        trend = result.get("trend", {})
        label = str(trend.get("label", "stable"))
        consecutive = int(trend.get("consecutive_count", 0))
        if label != "stable" and consecutive >= TREND_HYSTERESIS_COUNT:
            published.append(
                bus.publish(
                    type=EventType.AGENT_CAPABILITY_TREND_UPDATED.value,
                    payload=make_trend_payload(
                        agent_id=aid,
                        task_type=task_type,
                        slope=float(trend.get("slope", 0.0)),
                        label=label,
                        momentum=float(trend.get("momentum", 0.0)),
                        consecutive_count=consecutive,
                    ),
                    caused_by=caused_by,
                )
            )
        forecast = result.get("forecast", {})
        predicted = float(forecast.get("predicted_capability", 0.0))
        current = float(forecast.get("current_capability", 0.0))
        if abs(predicted - current) >= 0.05:
            published.append(
                bus.publish(
                    type=EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value,
                    payload=make_forecast_payload(
                        agent_id=aid,
                        task_type=task_type,
                        horizon=int(forecast.get("horizon", FORECAST_DEFAULT_HORIZON)),
                        predicted_capability=predicted,
                        confidence=float(forecast.get("confidence", 0.0)),
                        current_capability=current,
                        delta=float(forecast.get("delta", 0.0)),
                    ),
                    caused_by=caused_by,
                )
            )
        return published

    def fusion_step(
        self,
        bus: RuntimeEventBus,
        context: RuntimeContext,
        project_path: str | None,
        scheduler_result: dict[str, Any],
        caused_by: str,
        limit: int,
    ) -> tuple[dict[str, Any] | None, str, list[EventRead]]:
        """Emit FUSION_COMPUTED + SIGNAL_CALIBRATED events."""
        from allbrain.capabilities import CapabilityManager
        from allbrain.fusion import FusionManager, make_calibration_payload, make_fusion_payload

        task_id = str(scheduler_result.get("summary", {}).get("task_id", caused_by)) if scheduler_result else caused_by

        resolved = project_path or getattr(context, "project_path", None)
        try:
            events = context.repository.list_events(project_path=resolved, limit=limit)
        except Exception as exc:
            logger.debug("Failed to load events for fusion step: %s", exc, exc_info=True)
            events = []

        cap_mgr = CapabilityManager()
        agent_ids = cap_mgr.known_keys(events)
        if not agent_ids:
            return None, caused_by, []

        fusion_mgr = FusionManager()
        fusion_events: list[EventRead] = []

        for k in sorted(agent_ids):
            aid, tt = k.split("::", 1)
            result = fusion_mgr.query(events, agent_id=aid, task_type=tt)

            sv = result.get("signal_vector", {})
            cal = result.get("calibrations", {})

            for ch in ["capability", "learning", "dynamics", "causal"]:
                ce = bus.publish(
                    type=EventType.SIGNAL_CALIBRATED.value,
                    payload=make_calibration_payload(
                        agent_id=aid,
                        task_type=tt,
                        channel=ch,
                        raw_mean=float(cal.get(ch, 0.0)),
                        normalized_value=float(cal.get(ch, 0.0)),
                        was_normalized=bool(cal.get(ch, 0.0) > 0),
                        sample_count=1,
                    ),
                    caused_by=caused_by,
                )
                fusion_events.append(ce)

            fe = bus.publish(
                type=EventType.FUSION_COMPUTED.value,
                payload=make_fusion_payload(
                    agent_id=aid,
                    task_type=tt,
                    unified_score=float(result["unified_score"]),
                    capability=float(sv.get("capability", 0.0)),
                    learning=float(sv.get("learning", 0.0)),
                    dynamics=float(sv.get("dynamics", 0.0)),
                    causal=float(sv.get("causal", 0.0)),
                ),
                caused_by=caused_by,
            )
            fusion_events.append(fe)

        summary = {"task_id": task_id, "agent_count": len(agent_ids), "fusion_count": len(fusion_events)}
        return summary, caused_by, fusion_events
