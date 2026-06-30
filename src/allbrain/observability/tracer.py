from __future__ import annotations

from collections import defaultdict

from allbrain.events import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.models.schemas import EventRead
from allbrain.observability.span import Span


class Tracer:
    def build_spans(self, events: list[EventRead]) -> list[Span]:
        spans: list[Span] = []
        events = canonical_event_sort(events)
        events_by_task: dict[str, list[EventRead]] = defaultdict(list)
        for event in events:
            task_id = _task_id(event)
            if task_id:
                events_by_task[task_id].append(event)

        for task_id, task_events in sorted(events_by_task.items()):
            trace_id = _workflow_id(task_events[0]) or task_id
            workflow_span_id = f"workflow:{trace_id}"
            task_span_id = f"task:{task_id}"
            start = min(e.created_at for e in task_events)
            end = max(e.created_at for e in task_events)
            spans.append(
                Span(
                    span_id=workflow_span_id,
                    trace_id=trace_id,
                    workflow_id=trace_id,
                    task_id=None,
                    node_id=None,
                    agent_id=None,
                    kind="workflow",
                    start_time=start,
                    end_time=end,
                    latency_ms=_latency_ms(start, end),
                    status=_status(task_events),
                    attributes={"task_count": 1},
                )
            )
            spans.append(
                Span(
                    span_id=task_span_id,
                    trace_id=trace_id,
                    workflow_id=trace_id,
                    task_id=task_id,
                    node_id=None,
                    agent_id=None,
                    kind="task",
                    start_time=start,
                    end_time=end,
                    latency_ms=_latency_ms(start, end),
                    status=_status(task_events),
                    parent_span_id=workflow_span_id,
                    attributes={"event_count": len(task_events)},
                )
            )
            spans.extend(self._execution_spans(task_events, trace_id=trace_id, parent_span_id=task_span_id))
            spans.extend(self._decision_spans(task_events, trace_id=trace_id, parent_span_id=task_span_id))
        spans.extend(self._governance_spans(events))
        return spans

    def trace_tree(self, events: list[EventRead]) -> dict[str, object]:
        spans = self.build_spans(events)
        children: dict[str | None, list[dict[str, object]]] = defaultdict(list)
        for span in spans:
            children[span.parent_span_id].append(span.to_dict())
        for grouped in children.values():
            grouped.sort(key=lambda item: (str(item["start_time"]), str(item["span_id"])))
        return {
            "spans": [span.to_dict() for span in spans],
            "roots": children[None],
            "children": {key: value for key, value in children.items() if key is not None},
        }

    def _execution_spans(
        self,
        events: list[EventRead],
        *,
        trace_id: str,
        parent_span_id: str,
    ) -> list[Span]:
        spans: list[Span] = []
        starts: dict[tuple[str | None, str | None], EventRead] = {}
        for event in events:
            if event.type == EventType.AGENT_EXECUTION_STARTED.value:
                starts[(_node_id(event), _agent_id(event))] = event
            elif event.type in {
                EventType.AGENT_EXECUTION_COMPLETED.value,
                EventType.AGENT_EXECUTION_FAILED.value,
            }:
                key = (_node_id(event), _agent_id(event))
                start_event = starts.get(key, event)
                status = "error" if event.type == EventType.AGENT_EXECUTION_FAILED.value else "ok"
                spans.append(
                    Span(
                        span_id=f"agent_execution:{event.id}",
                        trace_id=trace_id,
                        workflow_id=trace_id,
                        task_id=_task_id(event),
                        node_id=_node_id(event),
                        agent_id=_agent_id(event),
                        kind="agent_execution",
                        start_time=start_event.created_at,
                        end_time=event.created_at,
                        latency_ms=_duration_from_payload(event)
                        or _latency_ms(start_event.created_at, event.created_at),
                        cost_usd=float(event.payload.get("cost_usd", 0.0) or 0.0),
                        status=status,
                        parent_span_id=parent_span_id,
                        attributes={"event_id": event.id, "error": event.payload.get("error")},
                    )
                )
        return spans

    def _decision_spans(
        self,
        events: list[EventRead],
        *,
        trace_id: str,
        parent_span_id: str,
    ) -> list[Span]:
        spans: list[Span] = []
        for event in events:
            if event.type != EventType.SELECTION_DECISION.value:
                continue
            spans.append(
                Span(
                    span_id=f"selection:{event.id}",
                    trace_id=trace_id,
                    workflow_id=trace_id,
                    task_id=_task_id(event),
                    node_id=_node_id(event),
                    agent_id=_agent_id(event),
                    kind="selection_decision",
                    start_time=event.created_at,
                    end_time=event.created_at,
                    latency_ms=0,
                    status="ok",
                    parent_span_id=parent_span_id,
                    attributes={
                        "total_score": event.payload.get("total_score"),
                        "reason": event.payload.get("reason"),
                        "breakdown": event.payload.get("breakdown", {}),
                    },
                )
            )
        return spans

    def _governance_spans(self, events: list[EventRead]) -> list[Span]:
        grouped: dict[str, list[EventRead]] = defaultdict(list)
        for event in events:
            review_id = event.payload.get("review_id")
            if event.type.startswith("governance_") and isinstance(review_id, str) and review_id:
                grouped[review_id].append(event)
        spans: list[Span] = []
        for review_id, review_events in sorted(grouped.items()):
            ordered = canonical_event_sort(review_events)
            start = min(e.created_at for e in ordered)
            end = max(e.created_at for e in ordered)
            status = "error" if any(event.payload.get("decision") == "reject_expansion" for event in ordered) else "ok"
            spans.append(
                Span(
                    span_id=f"governance_review:{review_id}",
                    trace_id=review_id,
                    workflow_id=None,
                    task_id=None,
                    node_id=None,
                    agent_id=None,
                    kind="governance_review",
                    start_time=start,
                    end_time=end,
                    latency_ms=_latency_ms(start, end),
                    status=status,
                    attributes={"event_count": len(ordered)},
                )
            )
        return spans


def _task_id(event: EventRead) -> str | None:
    value = event.payload.get("task_id")
    return value if isinstance(value, str) and value else None


def _workflow_id(event: EventRead) -> str | None:
    value = event.payload.get("workflow_id") or event.payload.get("root_task_id") or _task_id(event)
    return value if isinstance(value, str) and value else None


def _node_id(event: EventRead) -> str | None:
    value = event.payload.get("node_id")
    return value if isinstance(value, str) and value else None


def _agent_id(event: EventRead) -> str | None:
    value = event.payload.get("agent_id") or event.agent_id
    return value if isinstance(value, str) and value else None


def _latency_ms(start, end) -> int:
    return max(0, int((end - start).total_seconds() * 1000))


def _duration_from_payload(event: EventRead) -> int | None:
    value = event.payload.get("duration_ms")
    return int(value) if isinstance(value, int | float) else None


def _status(events: list[EventRead]) -> str:
    if any(event.type in {EventType.TASK_FAILED.value, EventType.AGENT_EXECUTION_FAILED.value} for event in events):
        return "error"
    if any(event.type == EventType.TASK_BLOCKED.value for event in events):
        return "blocked"
    return "ok"
