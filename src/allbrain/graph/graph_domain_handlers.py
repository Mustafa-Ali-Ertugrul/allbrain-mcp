from __future__ import annotations

from typing import Any

from allbrain.events import EventType
from allbrain.graph.graph_node_helpers import _add_edge, _event_node_id
from allbrain.models.schemas import EventRead


def _add_collaboration_graph(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    payload = event.payload
    collaboration_id = payload.get("collaboration_id")
    if event.type.startswith("collaboration_") and isinstance(collaboration_id, str):
        cid = f"collaboration:{collaboration_id}"
        nodes[cid] = {
            "id": cid,
            "type": "collaboration",
            "collaboration_id": collaboration_id,
            "status": event.type.replace("collaboration_", ""),
        }
        task_id = payload.get("task_id")
        if isinstance(task_id, str):
            nodes.setdefault(f"task:{task_id}", {"id": f"task:{task_id}", "type": "task", "task_id": task_id})
            _add_edge(edges, cid, f"task:{task_id}", "flow")
    delegation_id = payload.get("delegation_id")
    if event.type.startswith("delegation_") and isinstance(delegation_id, str):
        did = f"delegation:{delegation_id}"
        nodes[did] = {
            "id": did,
            "type": "delegation",
            "delegation_id": delegation_id,
            "status": event.type.replace("delegation_", ""),
        }
        from_agent = payload.get("from_agent")
        to_agent = payload.get("to_agent")
        if isinstance(from_agent, str) and isinstance(to_agent, str):
            nodes.setdefault(
                f"agent:{from_agent}", {"id": f"agent:{from_agent}", "type": "agent", "agent_id": from_agent}
            )
            nodes.setdefault(f"agent:{to_agent}", {"id": f"agent:{to_agent}", "type": "agent", "agent_id": to_agent})
            _add_edge(edges, f"agent:{from_agent}", did, "delegated_to")
            _add_edge(edges, did, f"agent:{to_agent}", "delegated_to")
    negotiation_id = payload.get("negotiation_id")
    if event.type.startswith("negotiation_") and isinstance(negotiation_id, str):
        nid = f"negotiation:{negotiation_id}"
        nodes[nid] = {
            "id": nid,
            "type": "negotiation",
            "negotiation_id": negotiation_id,
            "status": event.type.replace("negotiation_", ""),
        }
    proposal_id = payload.get("proposal_id")
    if event.type.startswith("proposal_") and isinstance(proposal_id, str):
        pid = f"proposal:{proposal_id}"
        nodes[pid] = {
            "id": pid,
            "type": "proposal",
            "proposal_id": proposal_id,
            "status": event.type.replace("proposal_", ""),
        }
        agent_id = payload.get("agent_id")
        if isinstance(agent_id, str):
            nodes.setdefault(f"agent:{agent_id}", {"id": f"agent:{agent_id}", "type": "agent", "agent_id": agent_id})
            _add_edge(edges, f"agent:{agent_id}", pid, "proposed_by")
        if isinstance(negotiation_id, str):
            nodes.setdefault(
                f"negotiation:{negotiation_id}",
                {"id": f"negotiation:{negotiation_id}", "type": "negotiation", "negotiation_id": negotiation_id},
            )
            _add_edge(edges, pid, f"negotiation:{negotiation_id}", "flow")
    consensus_id = payload.get("consensus_id")
    if event.type in {
        EventType.VOTE_CAST.value,
        EventType.CONSENSUS_REACHED.value,
        EventType.CONSENSUS_FAILED.value,
    } and isinstance(consensus_id, str):
        cid = f"consensus:{consensus_id}"
        nodes.setdefault(cid, {"id": cid, "type": "consensus", "consensus_id": consensus_id})
        if event.type == EventType.VOTE_CAST.value:
            vote_id = f"vote:{event.id}"
            nodes[vote_id] = {"id": vote_id, "type": "vote", "consensus_id": consensus_id, "vote": payload.get("vote")}
            agent_id = payload.get("agent_id")
            if isinstance(agent_id, str):
                nodes.setdefault(
                    f"agent:{agent_id}", {"id": f"agent:{agent_id}", "type": "agent", "agent_id": agent_id}
                )
                _add_edge(edges, f"agent:{agent_id}", vote_id, "voted_for")
            _add_edge(edges, vote_id, cid, "voted_for")
        else:
            nodes[cid]["status"] = event.type.replace("consensus_", "")
    if event.type == EventType.SUPERVISOR_INTERVENTION.value:
        sid = f"supervisor_action:{event.id}"
        nodes[sid] = {
            "id": sid,
            "type": "supervisor_action",
            "supervisor_id": payload.get("supervisor_id"),
            "action": payload.get("action"),
        }
        supervisor_id = payload.get("supervisor_id")
        if isinstance(supervisor_id, str):
            nodes.setdefault(
                f"agent:{supervisor_id}", {"id": f"agent:{supervisor_id}", "type": "agent", "agent_id": supervisor_id}
            )
            _add_edge(edges, f"agent:{supervisor_id}", sid, "supervised_by")


def _add_learning_graph(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    payload = event.payload
    cycle_id = payload.get("cycle_id")
    if event.type.startswith("learning_cycle_") and isinstance(cycle_id, str):
        node_id = f"learning_event:{cycle_id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "learning_event",
            "cycle_id": cycle_id,
            "status": event.type.replace("learning_cycle_", ""),
        }
    pattern_id = payload.get("pattern_id")
    if event.type == EventType.ORGANIZATIONAL_PATTERN_DISCOVERED.value and isinstance(pattern_id, str):
        node_id = f"optimization:{pattern_id}"
        nodes[node_id] = {"id": node_id, "type": "optimization", "pattern_id": pattern_id, "kind": payload.get("kind")}
        for source_event_id in payload.get("source_event_ids", []):
            if isinstance(source_event_id, str):
                source = _event_node_id([], source_event_id)
                if source:
                    _add_edge(edges, source, node_id, "learned_from")
    recommendation_id = payload.get("recommendation_id")
    if event.type.startswith("recommendation_") and isinstance(recommendation_id, str):
        node_id = f"recommendation:{recommendation_id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "recommendation",
            "recommendation_id": recommendation_id,
            "status": event.type.replace("recommendation_", ""),
            "kind": payload.get("kind"),
        }
        subject = payload.get("subject")
        if isinstance(subject, str):
            target = f"recommendation_subject:{subject}"
            nodes.setdefault(target, {"id": target, "type": "recommendation_subject", "subject": subject})
            _add_edge(edges, node_id, target, "recommends")
    policy_update_id = payload.get("policy_update_id")
    if event.type.startswith("policy_update_") and isinstance(policy_update_id, str):
        node_id = f"policy_update:{policy_update_id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "policy_update",
            "policy_update_id": policy_update_id,
            "status": event.type.replace("policy_update_", ""),
        }
        recommendation_id = payload.get("recommendation_id")
        if isinstance(recommendation_id, str):
            rec_id = f"recommendation:{recommendation_id}"
            nodes.setdefault(rec_id, {"id": rec_id, "type": "recommendation", "recommendation_id": recommendation_id})
            _add_edge(edges, rec_id, node_id, "influences")
        _add_edge(edges, node_id, "policy:agent_selection", "improves")
        nodes.setdefault(
            "policy:agent_selection", {"id": "policy:agent_selection", "type": "policy", "policy_id": "agent_selection"}
        )


def _add_governance_graph(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    payload = event.payload
    review_id = payload.get("review_id")
    if not isinstance(review_id, str):
        return
    review_node = f"governance_review:{review_id}"
    nodes.setdefault(review_node, {"id": review_node, "type": "governance_review", "review_id": review_id})
    if event.type == EventType.GOVERNANCE_REVIEW_INITIATED.value:
        nodes[review_node].update(
            {
                "status": "initiated",
                "trigger_source": payload.get("trigger_source"),
                "system_area": payload.get("system_area"),
            }
        )
        proposal_batch_id = payload.get("proposal_batch_id")
        if isinstance(proposal_batch_id, str):
            batch_node = f"evolution_batch:{proposal_batch_id}"
            nodes.setdefault(batch_node, {"id": batch_node, "type": "evolution_batch", "batch_id": proposal_batch_id})
            _add_edge(edges, batch_node, review_node, "governed_by")
    elif event.type == EventType.GOVERNANCE_ALIGNMENT_EVALUATED.value:
        node_id = f"alignment_report:{payload.get('report_id') or event.id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "alignment_report",
            "review_id": review_id,
            "alignment_score": payload.get("alignment_score"),
        }
        _add_edge(edges, review_node, node_id, "evaluates")
    elif event.type == EventType.GOVERNANCE_TRAJECTORY_SIMULATED.value:
        node_id = f"system_trajectory:{payload.get('trajectory_id') or event.id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "system_trajectory",
            "review_id": review_id,
            "trajectory_score": payload.get("trajectory_score"),
        }
        _add_edge(edges, review_node, node_id, "simulates")
    elif event.type == EventType.GOVERNANCE_AUTONOMY_ASSESSED.value:
        node_id = f"autonomy_decision:{payload.get('decision_id') or event.id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "autonomy_decision",
            "review_id": review_id,
            "autonomy_level_allowed": payload.get("autonomy_level_allowed"),
        }
        _add_edge(edges, review_node, node_id, "assesses")
    elif event.type == EventType.GOVERNANCE_DECISION_SYNTHESIZED.value:
        decision_id = payload.get("decision_id") or event.id
        node_id = f"governance_decision:{decision_id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "governance_decision",
            "review_id": review_id,
            "decision_id": decision_id,
            "decision": payload.get("decision"),
        }
        _add_edge(edges, review_node, node_id, "decides")
    elif event.type == EventType.GOVERNANCE_CONSTRAINTS_APPLIED.value:
        node_id = f"governance_constraint:{review_id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "governance_constraint",
            "review_id": review_id,
            "constraints": payload.get("constraints", []),
        }
        nodes.setdefault(
            "policy:autonomous_governance",
            {"id": "policy:autonomous_governance", "type": "policy", "policy_id": "autonomous_governance"},
        )
        _add_edge(edges, review_node, node_id, "constrains")
        _add_edge(edges, node_id, "policy:autonomous_governance", "updates")
    elif event.type == EventType.GOVERNANCE_POST_CHECK_COMPLETED.value:
        node_id = f"governance_post_check:{review_id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "governance_post_check",
            "review_id": review_id,
            "status": payload.get("status"),
        }
        _add_edge(edges, review_node, node_id, "verifies")


def _add_runtime_core_graph(nodes: dict[str, dict[str, Any]], edges: list[dict[str, str]], event: EventRead) -> None:
    payload = event.payload
    run_id = payload.get("run_id")
    if not isinstance(run_id, str):
        return
    run_node = f"pipeline_run:{run_id}"
    nodes.setdefault(run_node, {"id": run_node, "type": "pipeline_run", "run_id": run_id})
    if event.type == EventType.PIPELINE_RUN_STARTED.value:
        nodes[run_node].update({"status": "INIT", "execute_mode": payload.get("execute_mode")})
    elif event.type == EventType.PIPELINE_STATE_CHANGED.value:
        state_node = f"pipeline_state:{event.id}"
        nodes[state_node] = {
            "id": state_node,
            "type": "pipeline_state",
            "run_id": run_id,
            "status": payload.get("new_status"),
        }
        nodes[run_node]["status"] = payload.get("new_status")
        _add_edge(edges, run_node, state_node, "transitions")
    elif event.type == EventType.OBJECTIVE_RECEIVED.value:
        objective = payload.get("objective", {})
        objective_id = (
            objective.get("objective_id") or objective.get("task_id") or run_id
            if isinstance(objective, dict)
            else run_id
        )
        node_id = f"objective:{objective_id}"
        nodes[node_id] = {"id": node_id, "type": "objective", "run_id": run_id, "objective": objective}
        _add_edge(edges, node_id, run_node, "starts")
    elif event.type == EventType.ECONOMIC_EVALUATION_COMPLETED.value:
        node_id = f"economic_evaluation:{event.id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "economic_evaluation",
            "run_id": run_id,
            "decision": payload.get("decision"),
        }
        _add_edge(edges, run_node, node_id, "evaluates")
    elif event.type == EventType.ARBITRATION_COMPLETED.value:
        node_id = f"runtime_arbitration:{event.id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "runtime_arbitration",
            "run_id": run_id,
            "action": payload.get("action"),
        }
        _add_edge(edges, run_node, node_id, "arbitrates")
    elif event.type == EventType.FINAL_DECISION_RECORDED.value:
        node_id = f"final_decision:{run_id}"
        nodes[node_id] = {"id": node_id, "type": "final_decision", "run_id": run_id, "action": payload.get("action")}
        _add_edge(edges, run_node, node_id, "decides")
    elif event.type == EventType.RUNTIME_FEEDBACK_RECORDED.value:
        node_id = f"runtime_feedback:{run_id}"
        nodes[node_id] = {"id": node_id, "type": "runtime_feedback", "run_id": run_id, "status": payload.get("status")}
        _add_edge(edges, run_node, node_id, "feeds_back")
    elif event.type == EventType.PREDICTION_ERROR_DETECTED.value:
        node_id = f"prediction_error:{event.id}"
        nodes[node_id] = {
            "id": node_id,
            "type": "prediction_error",
            "run_id": run_id,
            "error_delta": payload.get("error_delta"),
        }
        _add_edge(edges, run_node, node_id, "learns_from")
