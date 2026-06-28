from __future__ import annotations

from collections import defaultdict

from allbrain.events import EventType
from allbrain.memory.semantic_memory import MemoryItem, SemanticMemory
from allbrain.models.schemas import EventRead
from allbrain.foundations import canonical_event_sort


class MemoryBuilder:
    def build(self, events: list[EventRead]) -> list[MemoryItem]:
        semantic = SemanticMemory()
        items: list[MemoryItem] = []
        events_by_task: dict[str, list[EventRead]] = defaultdict(list)
        for event in canonical_event_sort(events):
            task_id = event.payload.get("task_id")
            if isinstance(task_id, str) and task_id:
                events_by_task[task_id].append(event)

        for task_id, task_events in sorted(events_by_task.items()):
            summary = self._task_summary(task_id, task_events)
            items.append(
                semantic.make_item(
                    id=f"workflow:{task_id}",
                    content=summary,
                    tags={"kind": "workflow", "task_id": task_id, "status": self._status(task_events), "agent": self._last_agent(task_events) or "unknown"},
                    timestamp=task_events[-1].created_at,
                    importance_score=self._importance(task_events),
                    source_event_ids=[event.id for event in task_events],
                )
            )
            failure = self._failure_pattern(task_id, task_events)
            if failure:
                items.append(
                    semantic.make_item(
                        id=f"failure:{task_id}",
                        content=failure,
                        tags={"kind": "failure_pattern", "task_id": task_id, "agent": self._failed_agent(task_events) or "unknown", "reason": self._failure_reason(task_events) or "unknown"},
                        timestamp=task_events[-1].created_at,
                        importance_score=0.9,
                        source_event_ids=[event.id for event in task_events],
                    )
                )
            fallback = self._fallback_pattern(task_id, task_events)
            if fallback:
                items.append(
                    semantic.make_item(
                        id=f"fallback:{task_id}",
                        content=fallback,
                        tags={"kind": "fallback_pattern", "task_id": task_id},
                        timestamp=task_events[-1].created_at,
                        importance_score=0.8,
                        source_event_ids=[event.id for event in task_events],
                    )
                )
        items.extend(self._collaboration_items(events, semantic))
        items.extend(self._organizational_items(events, semantic))
        items.extend(self._governance_items(events, semantic))
        items.extend(self._runtime_core_items(events, semantic))
        return items

    def _task_summary(self, task_id: str, events: list[EventRead]) -> str:
        goal = next((event.payload.get("goal") for event in events if event.payload.get("goal")), task_id)
        status = self._status(events)
        agents = ", ".join(dict.fromkeys(agent for event in events if (agent := _agent(event))))
        failure = self._failure_reason(events)
        return f"task {task_id}: {goal}; status={status}; agents={agents or 'unknown'}; failure={failure or 'none'}"

    def _status(self, events: list[EventRead]) -> str:
        if any(event.type == EventType.TASK_COMPLETED.value for event in events):
            return "success"
        if any(event.type in {EventType.TASK_FAILED.value, EventType.AGENT_EXECUTION_FAILED.value} for event in events):
            return "failed"
        if any(event.type == EventType.TASK_BLOCKED.value for event in events):
            return "blocked"
        return "active"

    def _importance(self, events: list[EventRead]) -> float:
        if self._status(events) == "failed":
            return 0.8
        if self._status(events) == "success":
            return 0.7
        return 0.4

    def _last_agent(self, events: list[EventRead]) -> str | None:
        for event in reversed(events):
            agent = _agent(event)
            if agent:
                return agent
        return None

    def _failure_reason(self, events: list[EventRead]) -> str | None:
        for event in reversed(events):
            if event.type in {EventType.TASK_FAILED.value, EventType.AGENT_EXECUTION_FAILED.value}:
                reason = event.payload.get("reason") or event.payload.get("error") or event.payload.get("error_type")
                if isinstance(reason, str) and reason:
                    return reason
        return None

    def _failed_agent(self, events: list[EventRead]) -> str | None:
        for event in reversed(events):
            if event.type in {EventType.TASK_FAILED.value, EventType.AGENT_EXECUTION_FAILED.value}:
                agent = _agent(event)
                if agent:
                    return agent
        return None

    def _failure_pattern(self, task_id: str, events: list[EventRead]) -> str | None:
        reason = self._failure_reason(events)
        agent = self._failed_agent(events)
        if not reason:
            return None
        return f"failure pattern task={task_id} agent={agent or 'unknown'} reason={reason}"

    def _fallback_pattern(self, task_id: str, events: list[EventRead]) -> str | None:
        assignments = [_agent(event) for event in events if event.type == EventType.TASK_ASSIGNED.value and _agent(event)]
        if len(assignments) < 2:
            return None
        return f"fallback pattern task={task_id}: {assignments[0]} -> {assignments[-1]} status={self._status(events)}"

    def _collaboration_items(self, events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
        grouped: dict[str, list[EventRead]] = defaultdict(list)
        for event in canonical_event_sort(events):
            collaboration_id = event.payload.get("collaboration_id")
            if isinstance(collaboration_id, str) and collaboration_id:
                grouped[collaboration_id].append(event)
        items: list[MemoryItem] = []
        for collaboration_id, collab_events in sorted(grouped.items()):
            status = "success" if any(event.type == EventType.COLLABORATION_COMPLETED.value for event in collab_events) else "failed" if any(event.type == EventType.COLLABORATION_FAILED.value for event in collab_events) else "active"
            agents = sorted({agent for event in collab_events if (agent := _agent(event))})
            objective = next((event.payload.get("objective") for event in collab_events if event.payload.get("objective")), collaboration_id)
            content = f"collaboration {collaboration_id}: {objective}; status={status}; agents={','.join(agents) or 'unknown'}"
            items.append(
                semantic.make_item(
                    id=f"collaboration:{collaboration_id}",
                    content=content,
                    tags={"kind": "collaboration", "collaboration_id": collaboration_id, "status": status},
                    timestamp=collab_events[-1].created_at,
                    importance_score=0.8 if status == "success" else 0.7,
                    source_event_ids=[event.id for event in collab_events],
                )
            )
        return items

    def _organizational_items(self, events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
        items: list[MemoryItem] = []
        for event in canonical_event_sort(events):
            if event.type == EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value:
                pattern_id = event.payload.get("pattern_id")
                kind = str(event.payload.get("kind") or "organizational_pattern")
                if isinstance(pattern_id, str):
                    content = f"organizational pattern {kind}: {event.payload.get('summary') or pattern_id}; confidence={event.payload.get('confidence', 0.0)}"
                    items.append(
                        semantic.make_item(
                            id=f"organizational_pattern:{pattern_id}",
                            content=content,
                            tags={"kind": kind, "pattern_id": pattern_id, "status": "discovered"},
                            timestamp=event.created_at,
                            importance_score=float(event.payload.get("confidence", 0.7) or 0.7),
                            source_event_ids=[event.id],
                        )
                    )
            elif event.type == EventType.RECOMMENDATION_GENERATED.value:
                recommendation_id = event.payload.get("recommendation_id")
                kind = str(event.payload.get("kind") or "recommendation")
                if isinstance(recommendation_id, str):
                    items.append(
                        semantic.make_item(
                            id=f"recommendation:{recommendation_id}",
                            content=f"recommendation {kind}: {event.payload.get('subject')}; confidence={event.payload.get('confidence', 0.0)}",
                            tags={"kind": "recommendation", "recommendation_kind": kind, "recommendation_id": recommendation_id},
                            timestamp=event.created_at,
                            importance_score=float(event.payload.get("confidence", 0.6) or 0.6),
                            source_event_ids=[event.id],
                        )
                    )
        return items

    def _governance_items(self, events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
        items: list[MemoryItem] = []
        for event in canonical_event_sort(events):
            if event.type == EventType.GOVERNANCE_DECISION_SYNTHESIZED.value:
                decision_id = event.payload.get("decision_id")
                if isinstance(decision_id, str):
                    decision = event.payload.get("decision")
                    review_id = event.payload.get("review_id")
                    content = f"governance decision {decision}: review={review_id}; alignment={event.payload.get('alignment_score')}; trajectory={event.payload.get('trajectory_score')}"
                    items.append(
                        semantic.make_item(
                            id=f"governance_decision:{decision_id}",
                            content=content,
                            tags={"kind": "governance_decision", "decision_id": decision_id, "review_id": str(review_id or ""), "decision": str(decision or "unknown")},
                            timestamp=event.created_at,
                            importance_score=float(event.payload.get("confidence", 0.7) or 0.7),
                            source_event_ids=[event.id],
                        )
                    )
            elif event.type == EventType.GOVERNANCE_ALIGNMENT_EVALUATED.value:
                report_id = event.payload.get("report_id")
                if isinstance(report_id, str):
                    items.append(
                        semantic.make_item(
                            id=f"alignment_report:{report_id}",
                            content=f"alignment report score={event.payload.get('alignment_score')}; drift={event.payload.get('long_term_drift_score')}; safety={event.payload.get('safety_alignment_score')}",
                            tags={"kind": "alignment_report", "report_id": report_id, "review_id": str(event.payload.get("review_id") or "")},
                            timestamp=event.created_at,
                            importance_score=1.0 - float(event.payload.get("alignment_score", 0.7) or 0.7),
                            source_event_ids=[event.id],
                        )
                    )
        return items

    def _runtime_core_items(self, events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
        items: list[MemoryItem] = []
        for event in canonical_event_sort(events):
            run_id = event.payload.get("run_id")
            if not isinstance(run_id, str):
                continue
            if event.type == EventType.FINAL_DECISION_RECORDED.value:
                items.append(
                    semantic.make_item(
                        id=f"runtime_final_decision:{run_id}",
                        content=f"runtime final decision action={event.payload.get('action')}; reason={event.payload.get('reason')}; confidence={event.payload.get('confidence')}",
                        tags={"kind": "runtime_final_decision", "run_id": run_id, "action": str(event.payload.get("action") or "unknown")},
                        timestamp=event.created_at,
                        importance_score=float(event.payload.get("confidence", 0.7) or 0.7),
                        source_event_ids=[event.id],
                    )
                )
            elif event.type == EventType.RUNTIME_FEEDBACK_RECORDED.value:
                items.append(
                    semantic.make_item(
                        id=f"runtime_feedback:{run_id}",
                        content=f"runtime feedback status={event.payload.get('status')}; mode={event.payload.get('execute_mode')}",
                        tags={"kind": "runtime_feedback", "run_id": run_id, "status": str(event.payload.get("status") or "unknown")},
                        timestamp=event.created_at,
                        importance_score=0.7,
                        source_event_ids=[event.id],
                    )
                )
            elif event.type == EventType.PREDICTION_ERROR_DETECTED.value:
                items.append(
                    semantic.make_item(
                        id=f"prediction_error:{event.id}",
                        content=f"prediction error delta={event.payload.get('error_delta')}; run={run_id}",
                        tags={"kind": "prediction_error", "run_id": run_id},
                        timestamp=event.created_at,
                        importance_score=0.9,
                        source_event_ids=[event.id],
                    )
                )
        return items


def _agent(event: EventRead) -> str | None:
    value = event.payload.get("agent_id") or event.payload.get("from_agent") or event.payload.get("to_agent") or event.agent_id
    return value if isinstance(value, str) and value else None
