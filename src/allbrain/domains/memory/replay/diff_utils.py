from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead


def _task_statuses(state: dict[str, Any]) -> dict[str, str]:
    return {task_id: task.get("status", "unknown") for task_id, task in state["tasks"].items()}


def _dict_delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = sorted(set(left) | set(right))
    return {key: {"left": left.get(key), "right": right.get(key)} for key in keys if left.get(key) != right.get(key)}


def _list_delta(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    return {"left_count": len(left), "right_count": len(right), "changed": left != right}


def diff(left: list[EventRead], right: list[EventRead], replay_fn) -> dict[str, Any]:
    left_state = replay_fn(left)["final_state"]
    right_state = replay_fn(right)["final_state"]
    return {
        "status_delta": _dict_delta(_task_statuses(left_state), _task_statuses(right_state)),
        "decision_delta": _list_delta(left_state["decisions"], right_state["decisions"]),
        "failure_delta": _list_delta(left_state["failures"], right_state["failures"]),
    }


def _copy_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "tasks": {key: dict(value) for key, value in state["tasks"].items()},
        "decisions": [dict(item) for item in state["decisions"]],
        "failures": [dict(item) for item in state["failures"]],
        "collaboration": dict(state.get("collaboration", {})),
        "organizational_learning": dict(state.get("organizational_learning", {})),
        "recommendations": dict(state.get("recommendations", {})),
        "policy_updates": dict(state.get("policy_updates", {})),
        "governance": dict(state.get("governance", {})),
        "runtime_core": dict(state.get("runtime_core", {})),
        "world": dict(state.get("world", {})),
        "counterfactual": dict(state.get("counterfactual", {})),
        "scenarios": dict(state.get("scenarios", {})),
        "foresight": dict(state.get("foresight", {})),
        "reasoning": dict(state.get("reasoning", {})),
        "uncertainty": dict(state.get("uncertainty", {})),
        "knowledge_gaps": dict(state.get("knowledge_gaps", {})),
        "information_seeking": dict(state.get("information_seeking", {})),
        "unknown_events": list(state.get("unknown_events", [])),
        "belief": dict(state.get("belief", {})),
        "contradiction": dict(state.get("contradiction", {})),
        "revision": dict(state.get("revision", {})),
        "evidence": dict(state.get("evidence", {})),
        "calibration": dict(state.get("calibration", {})),
        "drift": dict(state.get("drift", {})),
        "reputation": dict(state.get("reputation", {})),
        "arbitration": dict(state.get("arbitration", {})),
        "telemetry": dict(state.get("telemetry", {})),
        "routing": dict(state.get("routing", {})),
        "capabilities": dict(state.get("capabilities", {})),
        "learning": dict(state.get("learning", {})),
        "dynamics": dict(state.get("dynamics", {})),
        "causal": dict(state.get("causal", {})),
        "fusion": dict(state.get("fusion", {})),
        "decision": dict(state.get("decision", {})),
        "meta_policy": dict(state.get("meta_policy", {})),
        "attribution": dict(state.get("attribution", {})),
        "attention": dict(state.get("attention", {})),
        "workspace": dict(state.get("workspace", {})),
        "episodic": dict(state.get("episodic", {})),
        "semantic": dict(state.get("semantic", {})),
        "resilience": dict(state.get("resilience", {})),
        "recovery_consensus": dict(state.get("recovery_consensus", {})),
        "failure_memory": dict(state.get("failure_memory", {})),
        "adaptive_recovery": dict(state.get("adaptive_recovery", {})),
        "predictive_failure": dict(state.get("predictive_failure", {})),
        "mitigation_learning": dict(state.get("mitigation_learning", {})),
        "learning_safety": dict(state.get("learning_safety", {})),
        "self_repair": dict(state.get("self_repair", {})),
        "policy_routing": dict(state.get("policy_routing", {})),
        "policy_competition": dict(state.get("policy_competition", {})),
        "soft_repair": dict(state.get("soft_repair", {})),
        "meta_scoring": dict(state.get("meta_scoring", {})),
        "self_play": dict(state.get("self_play", {})),
        "meta_optimizer": dict(state.get("meta_optimizer", {})),
        "meta_meta_scoring": dict(state.get("meta_meta_scoring", {})),
        "objective_system": dict(state.get("objective_system", {})),
        "tradeoff": dict(state.get("tradeoff", {})),
        "value_alignment": dict(state.get("value_alignment", {})),
        "foundations": dict(state.get("foundations", {})),
    }
