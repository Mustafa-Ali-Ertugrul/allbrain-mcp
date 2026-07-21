from __future__ import annotations

from collections import defaultdict

from allbrain.events import EventType
from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.domains.memory.memory.memory_helpers import _agent
from allbrain.domains.memory.memory.semantic_memory import MemoryItem, SemanticMemory
from allbrain.models.schemas import EventRead


def _session_items(events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    for event in canonical_event_sort(events):
        if event.type != EventType.SESSION_SUMMARY.value:
            continue
        payload = event.payload
        session_id = str(payload.get("session_id") or event.session_id)
        goals = "; ".join(str(value) for value in payload.get("goals", []) if value)
        files = ", ".join(str(value) for value in payload.get("files", []) if value)
        tools = ", ".join(str(value) for value in payload.get("tools", []) if value)
        errors = "; ".join(str(value) for value in payload.get("errors", []) if value)
        status = str(payload.get("status") or "unknown")
        agent = str(payload.get("agent") or event.agent_id or "unknown")
        content = (
            f"session {session_id}: status={status}; agent={agent}; "
            f"goals={goals or 'none'}; files={files or 'none'}; "
            f"tools={tools or 'none'}; errors={errors or 'none'}"
        )
        items.append(
            semantic.make_item(
                id=f"session:{session_id}",
                content=content,
                tags={"kind": "session", "session_id": session_id, "status": status, "agent": agent},
                timestamp=event.created_at,
                importance_score=0.8 if errors else 0.65,
                source_event_ids=[event.id],
            )
        )
    return items


def _goal_items(events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    for event in canonical_event_sort(events):
        if event.type != EventType.GOAL_SET.value or event.payload.get("task_id"):
            continue
        goal = event.payload.get("goal") or event.payload.get("description") or event.payload.get("summary")
        if not isinstance(goal, str) or not goal:
            continue
        items.append(
            semantic.make_item(
                id=f"goal:{event.id}",
                content=f"goal: {goal}; agent={event.agent_id or 'unknown'}",
                tags={"kind": "goal", "status": str(event.payload.get("status") or "active")},
                timestamp=event.created_at,
                importance_score=0.7,
                source_event_ids=[event.id],
            )
        )
    return items


def _file_modification_items(events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
    grouped: dict[str, list[EventRead]] = defaultdict(list)
    for event in canonical_event_sort(events):
        if event.type != EventType.FILE_MODIFIED.value:
            continue
        path = event.file_path
        if isinstance(path, str) and path:
            grouped[path].append(event)
    items: list[MemoryItem] = []
    for path, file_events in sorted(grouped.items()):
        change_kinds = sorted({str(event.payload.get("change_kind") or "unknown") for event in file_events})
        agents = sorted({agent for event in file_events if (agent := _agent(event))})
        confidences = sorted({str(event.payload.get("confidence") or "unknown") for event in file_events})
        content = (
            f"file {path}: changes={','.join(change_kinds)}; "
            f"agents={','.join(agents) or 'unknown'}; "
            f"confidence={','.join(confidences)}; count={len(file_events)}"
        )
        items.append(
            semantic.make_item(
                id=f"file:{path}",
                content=content,
                tags={
                    "kind": "file_modification",
                    "file_path": path,
                    "change_kinds": ",".join(change_kinds),
                    "agents": ",".join(agents) or "unknown",
                },
                timestamp=file_events[-1].created_at,
                importance_score=0.65,
                source_event_ids=[event.id for event in file_events],
            )
        )
    return items


def _collaboration_items(events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
    grouped: dict[str, list[EventRead]] = defaultdict(list)
    for event in canonical_event_sort(events):
        collaboration_id = event.payload.get("collaboration_id")
        if isinstance(collaboration_id, str) and collaboration_id:
            grouped[collaboration_id].append(event)
    items: list[MemoryItem] = []
    for collaboration_id, collab_events in sorted(grouped.items()):
        status = (
            "success"
            if any(event.type == EventType.COLLABORATION_COMPLETED.value for event in collab_events)
            else "failed"
            if any(event.type == EventType.COLLABORATION_FAILED.value for event in collab_events)
            else "active"
        )
        agents = sorted({agent for event in collab_events if (agent := _agent(event))})
        objective = next(
            (event.payload.get("objective") for event in collab_events if event.payload.get("objective")),
            collaboration_id,
        )
        agents_str = ",".join(agents) or "unknown"
        content = f"collaboration {collaboration_id}: {objective}; status={status}; agents={agents_str}"
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


def _organizational_items(events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    for event in canonical_event_sort(events):
        if event.type == EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value:
            pattern_id = event.payload.get("pattern_id")
            kind = str(event.payload.get("kind") or "organizational_pattern")
            if isinstance(pattern_id, str):
                summary = event.payload.get("summary") or pattern_id
                confidence = event.payload.get("confidence", 0.0)
                content = f"organizational pattern {kind}: {summary}; confidence={confidence}"
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
                        content=(
                            f"recommendation {kind}: {event.payload.get('subject')}; "
                            f"confidence={event.payload.get('confidence', 0.0)}"
                        ),
                        tags={
                            "kind": "recommendation",
                            "recommendation_kind": kind,
                            "recommendation_id": recommendation_id,
                        },
                        timestamp=event.created_at,
                        importance_score=float(event.payload.get("confidence", 0.6) or 0.6),
                        source_event_ids=[event.id],
                    )
                )
    return items


def _governance_items(events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    for event in canonical_event_sort(events):
        if event.type == EventType.GOVERNANCE_DECISION_SYNTHESIZED.value:
            decision_id = event.payload.get("decision_id")
            if isinstance(decision_id, str):
                decision = event.payload.get("decision")
                review_id = event.payload.get("review_id")
                alignment = event.payload.get("alignment_score")
                trajectory = event.payload.get("trajectory_score")
                content = (
                    f"governance decision {decision}: review={review_id}; "
                    f"alignment={alignment}; trajectory={trajectory}"
                )
                items.append(
                    semantic.make_item(
                        id=f"governance_decision:{decision_id}",
                        content=content,
                        tags={
                            "kind": "governance_decision",
                            "decision_id": decision_id,
                            "review_id": str(review_id or ""),
                            "decision": str(decision or "unknown"),
                        },
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
                        content=(
                            f"alignment report score={event.payload.get('alignment_score')}; "
                            f"drift={event.payload.get('long_term_drift_score')}; "
                            f"safety={event.payload.get('safety_alignment_score')}"
                        ),
                        tags={
                            "kind": "alignment_report",
                            "report_id": report_id,
                            "review_id": str(event.payload.get("review_id") or ""),
                        },
                        timestamp=event.created_at,
                        importance_score=1.0 - float(event.payload.get("alignment_score", 0.7) or 0.7),
                        source_event_ids=[event.id],
                    )
                )
    return items


def _runtime_core_items(events: list[EventRead], semantic: SemanticMemory) -> list[MemoryItem]:
    items: list[MemoryItem] = []
    for event in canonical_event_sort(events):
        run_id = event.payload.get("run_id")
        if not isinstance(run_id, str):
            continue
        if event.type == EventType.FINAL_DECISION_RECORDED.value:
            items.append(
                semantic.make_item(
                    id=f"runtime_final_decision:{run_id}",
                    content=(
                        f"runtime final decision action={event.payload.get('action')}; "
                        f"reason={event.payload.get('reason')}; confidence={event.payload.get('confidence')}"
                    ),
                    tags={
                        "kind": "runtime_final_decision",
                        "run_id": run_id,
                        "action": str(event.payload.get("action") or "unknown"),
                    },
                    timestamp=event.created_at,
                    importance_score=float(event.payload.get("confidence", 0.7) or 0.7),
                    source_event_ids=[event.id],
                )
            )
        elif event.type == EventType.RUNTIME_FEEDBACK_RECORDED.value:
            items.append(
                semantic.make_item(
                    id=f"runtime_feedback:{run_id}",
                    content=(
                        f"runtime feedback status={event.payload.get('status')}; "
                        f"mode={event.payload.get('execute_mode')}"
                    ),
                    tags={
                        "kind": "runtime_feedback",
                        "run_id": run_id,
                        "status": str(event.payload.get("status") or "unknown"),
                    },
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
