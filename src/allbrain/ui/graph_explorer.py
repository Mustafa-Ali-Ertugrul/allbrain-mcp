from __future__ import annotations

from typing import Any

from allbrain.graph import GraphQueryEngine, WorkflowGraphBuilder
from allbrain.models.schemas import EventRead


class GraphExplorer:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        graph = WorkflowGraphBuilder().build(events)
        query = GraphQueryEngine(graph)
        event_details = _event_details(events)
        return {
            "nodes": [
                {
                    "id": node_id,
                    "label": node_id,
                    "data": node,
                    "event_details": event_details.get(node_id, []),
                    "click": {"node_id": node_id, "event_count": len(event_details.get(node_id, []))},
                }
                for node_id, node in graph["nodes"].items()
            ],
            "edges": graph["edges"],
            "path_traces": {
                "failed": query.find_paths(failed=True),
            },
            "has_cycle": graph["has_cycle"],
        }


def _event_details(events: list[EventRead]) -> dict[str, list[dict[str, Any]]]:
    details: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        node_ids = _node_ids_for_event(event)
        detail = {
            "event_id": event.id,
            "type": event.type,
            "created_at": event.created_at.isoformat(),
            "agent_id": event.payload.get("agent_id") or event.agent_id,
            "payload": dict(event.payload),
        }
        for node_id in node_ids:
            details.setdefault(node_id, []).append(detail)
    return details


def _node_ids_for_event(event: EventRead) -> list[str]:
    node_ids: list[str] = []
    task_id = event.payload.get("task_id")
    workflow_id = event.payload.get("workflow_id") or event.payload.get("root_task_id") or task_id
    agent_id = event.payload.get("agent_id") or event.agent_id
    if isinstance(workflow_id, str) and workflow_id:
        node_ids.append(f"workflow:{workflow_id}")
    if isinstance(task_id, str) and task_id:
        node_ids.append(f"task:{task_id}")
    if isinstance(agent_id, str) and agent_id:
        node_ids.append(f"agent:{agent_id}")
    if event.type == "selection_decision":
        node_ids.append(f"selection:{event.id}")
    if event.type.startswith("agent_execution_"):
        node_ids.append(f"agent_execution:{event.id}")
    review_id = event.payload.get("review_id")
    if isinstance(review_id, str) and review_id:
        node_ids.append(f"governance_review:{review_id}")
    decision_id = event.payload.get("decision_id")
    if event.type == "governance_decision_synthesized" and isinstance(decision_id, str) and decision_id:
        node_ids.append(f"governance_decision:{decision_id}")
    run_id = event.payload.get("run_id")
    if isinstance(run_id, str) and run_id:
        node_ids.append(f"pipeline_run:{run_id}")
        if event.type == "final_decision_recorded":
            node_ids.append(f"final_decision:{run_id}")
        elif event.type == "runtime_feedback_recorded":
            node_ids.append(f"runtime_feedback:{run_id}")
    return node_ids
