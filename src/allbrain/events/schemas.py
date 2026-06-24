from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    GOAL_SET = "goal_set"
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    SELECTION_DECISION = "selection_decision"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    FILE_MODIFIED = "file_modified"
    FAILURE = "failure"
    TASK_BLOCKED = "task_blocked"
    TASK_DEPENDENCY_ADDED = "task_dependency_added"
    TASK_PRIORITY_CHANGED = "task_priority_changed"
    HANDOFF_CREATED = "handoff_created"
    TOOL_CALL = "tool_call"
    SUBTASK_CREATED = "subtask_created"
    SUBTASK_STARTED = "subtask_started"
    SUBTASK_COMPLETED = "subtask_completed"
    SUBTASK_FAILED = "subtask_failed"
    WORKFLOW_CREATED = "workflow_created"
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    RESULT_AGGREGATED = "result_aggregated"
    WORKFLOW_STATE_CHANGED = "workflow_state_changed"
    RETRY_SCHEDULED = "retry_scheduled"
    AGENT_REGISTERED = "agent_registered"
    AGENT_HEALTH_CHANGED = "agent_health_changed"
    AGENT_EXECUTION_STARTED = "agent_execution_started"
    AGENT_EXECUTION_COMPLETED = "agent_execution_completed"
    AGENT_EXECUTION_FAILED = "agent_execution_failed"
    COST_CEILING_EXCEEDED = "cost_ceiling_exceeded"
    CAPABILITY_UPDATED = "capability_updated"
    QUEUE_ITEM_ENQUEUED = "queue_item_enqueued"
    QUEUE_ITEM_DEQUEUED = "queue_item_dequeued"
    WORKER_STARTED = "worker_started"
    WORKER_STOPPED = "worker_stopped"
    DUPLICATE_DETECTED = "duplicate_detected"
    IDEMPOTENCY_KEY_RECORDED = "idempotency_key_recorded"
    LEASE_ACQUIRED = "lease_acquired"
    LEASE_RENEWED = "lease_renewed"
    LEASE_RELEASED = "lease_released"
    LEASE_EXPIRED = "lease_expired"
    TASK_REQUEUED = "task_requeued"
    WORKER_HEARTBEAT = "worker_heartbeat"
    WORKER_STALE = "worker_stale"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    RECOVERY_FAILED = "recovery_failed"
    RESOURCE_CLOSED = "resource_closed"
    SNAPSHOT_RESTORED = "snapshot_restored"
    CLUSTER_NODE_REGISTERED = "cluster_node_registered"
    WORKER_REGISTERED = "worker_registered"
    QUEUE_BACKEND_OUTAGE = "queue_backend_outage"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_HALF_OPENED = "circuit_breaker_half_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    RETRY_ATTEMPTED = "retry_attempted"
    BULKHEAD_REJECTED = "bulkhead_rejected"
    TEAM_CREATED = "team_created"
    COLLABORATION_STARTED = "collaboration_started"
    COLLABORATION_COMPLETED = "collaboration_completed"
    COLLABORATION_FAILED = "collaboration_failed"
    DELEGATION_CREATED = "delegation_created"
    DELEGATION_COMPLETED = "delegation_completed"
    DELEGATION_FAILED = "delegation_failed"
    NEGOTIATION_STARTED = "negotiation_started"
    NEGOTIATION_COMPLETED = "negotiation_completed"
    NEGOTIATION_TIMEOUT = "negotiation_timeout"
    PROPOSAL_CREATED = "proposal_created"
    PROPOSAL_ACCEPTED = "proposal_accepted"
    PROPOSAL_REJECTED = "proposal_rejected"
    VOTE_CAST = "vote_cast"
    CONSENSUS_REACHED = "consensus_reached"
    CONSENSUS_FAILED = "consensus_failed"
    SUPERVISOR_INTERVENTION = "supervisor_intervention"
    LEARNING_CYCLE_STARTED = "learning_cycle_started"
    LEARNING_CYCLE_COMPLETED = "learning_cycle_completed"
    RECOMMENDATION_GENERATED = "recommendation_generated"
    RECOMMENDATION_APPLIED = "recommendation_applied"
    RECOMMENDATION_REJECTED = "recommendation_rejected"
    POLICY_UPDATE_PROPOSED = "policy_update_proposed"
    POLICY_UPDATE_APPROVED = "policy_update_approved"
    POLICY_UPDATE_REJECTED = "policy_update_rejected"
    ORGANIZATIONAL_PATTERN_DISCOVERED = "organizational_pattern_discovered"
    GOVERNANCE_REVIEW_INITIATED = "governance_review_initiated"
    GOVERNANCE_ALIGNMENT_EVALUATED = "governance_alignment_evaluated"
    GOVERNANCE_TRAJECTORY_SIMULATED = "governance_trajectory_simulated"
    GOVERNANCE_AUTONOMY_ASSESSED = "governance_autonomy_assessed"
    GOVERNANCE_DECISION_SYNTHESIZED = "governance_decision_synthesized"
    GOVERNANCE_CONSTRAINTS_APPLIED = "governance_constraints_applied"
    GOVERNANCE_SYSTEM_UPDATED = "governance_system_updated"
    GOVERNANCE_POST_CHECK_COMPLETED = "governance_post_check_completed"
    PIPELINE_RUN_STARTED = "pipeline_run_started"
    PIPELINE_STATE_CHANGED = "pipeline_state_changed"
    OBJECTIVE_RECEIVED = "objective_received"
    GOVERNANCE_PRECHECK_COMPLETED = "governance_precheck_completed"
    ECONOMIC_EVALUATION_COMPLETED = "economic_evaluation_completed"
    STRATEGIC_PLAN_CREATED = "strategic_plan_created"
    GOAL_DECOMPOSITION_COMPLETED = "goal_decomposition_completed"
    EXECUTION_PLAN_CREATED = "execution_plan_created"
    ARBITRATION_COMPLETED = "arbitration_completed"
    FINAL_DECISION_RECORDED = "final_decision_recorded"
    SCHEDULER_EXECUTION_STARTED = "scheduler_execution_started"
    RUNTIME_FEEDBACK_RECORDED = "runtime_feedback_recorded"
    PREDICTION_ERROR_DETECTED = "prediction_error_detected"
    MODEL_UPDATE_PROPOSED = "model_update_proposed"
    PIPELINE_RUN_COMPLETED = "pipeline_run_completed"
    PIPELINE_RUN_FAILED = "pipeline_run_failed"
    WORLD_STATE_OBSERVED = "world_state_observed"
    WORLD_SIMULATION_RUN = "world_simulation_run"
    COUNTERFACTUAL_GENERATED = "counterfactual_generated"
    COUNTERFACTUAL_EVALUATED = "counterfactual_evaluated"
    COUNTERFACTUAL_RECOMMENDATION = "counterfactual_recommendation"
    SCENARIO_GENERATED = "scenario_generated"
    SCENARIO_EVALUATED = "scenario_evaluated"
    SCENARIO_RECOMMENDED = "scenario_recommended"
    FORESIGHT_GENERATED = "foresight_generated"
    FORESIGHT_EVALUATED = "foresight_evaluated"
    FORESIGHT_RECOMMENDED = "foresight_recommended"
    META_REASONING_STARTED = "meta_reasoning_started"
    META_REASONING_COMPLETED = "meta_reasoning_completed"
    DECISION_EXPLAINED = "decision_explained"
    UNCERTAINTY_ESTIMATED = "uncertainty_estimated"
    KNOWLEDGE_GAP_DETECTED = "knowledge_gap_detected"
    CONFIDENCE_CALIBRATED = "confidence_calibrated"
    INFORMATION_NEED_DETECTED = "information_need_detected"
    INFORMATION_ACTION_SELECTED = "information_action_selected"
    INFORMATION_GAIN_ESTIMATED = "information_gain_estimated"
    BELIEF_COMPUTED = "belief_computed"
    CONTRADICTION_DETECTED = "contradiction_detected"
    BELIEF_REVISED = "belief_revised"
    UNCERTAINTY_COMPUTED = "uncertainty_computed"
    EVIDENCE_RECORDED = "evidence_recorded"
    EVIDENCE_DECAYED = "evidence_decayed"
    TRUST_UPDATED = "trust_updated"
    CALIBRATION_UPDATED = "calibration_updated"
    BELIEF_DRIFT_DETECTED = "belief_drift_detected"
    AGENT_REPUTATION_UPDATED = "agent_reputation_updated"
    AGENT_VOTE_CAST = "agent_vote_cast"
    AGENT_CONSENSUS_REACHED = "agent_consensus_reached"
    AGENT_ARBITRATION_DECISION = "agent_arbitration_decision"
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    AGENT_RUNTIME_UPDATED = "agent_runtime_updated"
    AGENT_SELECTION_REQUESTED = "agent_selection_requested"
    AGENT_SELECTION_SCORED = "agent_selection_scored"
    AGENT_SELECTED = "agent_selected"
    AGENT_CAPABILITY_REGISTERED = "agent_capability_registered"
    TASK_CLASSIFIED = "task_classified"
    CAPABILITY_MATCHED = "capability_matched"
    AGENT_CAPABILITY_OBSERVED = "agent_capability_observed"
    AGENT_CAPABILITY_LEARNED = "agent_capability_learned"
    AGENT_CAPABILITY_DECAYED = "agent_capability_decayed"
    AGENT_CAPABILITY_DRIFT_DETECTED = "agent_capability_drift_detected"
    AGENT_CAPABILITY_TREND_UPDATED = "agent_capability_trend_updated"
    AGENT_CAPABILITY_FORECAST_UPDATED = "agent_capability_forecast_updated"
    AGENT_COUNTERFACTUAL_RUN = "agent_counterfactual_run"
    AGENT_CAUSAL_IMPACT_RECORDED = "agent_causal_impact_recorded"
    FUSION_COMPUTED = "fusion_computed"
    SIGNAL_CALIBRATED = "signal_calibrated"
    DECISION_COMPUTED = "decision_computed"
    POLICY_EVALUATED = "policy_evaluated"
    POLICY_UPDATED = "policy_updated"
    POLICY_DIVERGENCE_DETECTED = "policy_divergence_detected"
    SIGNAL_CREDIT_ASSIGNED = "signal_credit_assigned"
    SIGNAL_ATTRIBUTION_UPDATED = "signal_attribution_updated"
    SIGNAL_IMPORTANCE_CHANGED = "signal_importance_changed"
    ATTENTION_ALLOCATED = "attention_allocated"
    RESOURCE_BUDGET_UPDATED = "resource_budget_updated"
    ATTENTION_REALLOCATED = "attention_reallocated"
    WORKSPACE_UPDATED = "workspace_updated"
    WORKSPACE_ITEM_ADDED = "workspace_item_added"
    WORKSPACE_ITEM_REMOVED = "workspace_item_removed"
    EPISODE_CREATED = "episode_created"
    EPISODE_RETRIEVED = "episode_retrieved"
    EPISODE_FORGOTTEN = "episode_forgotten"
    SEMANTIC_CONCEPT_CREATED = "semantic_concept_created"
    SEMANTIC_CONCEPT_UPDATED = "semantic_concept_updated"
    SEMANTIC_CONCEPT_FORGOTTEN = "semantic_concept_forgotten"


SemanticEventType = {
    EventType.GOAL_SET,
    EventType.TASK_CREATED,
    EventType.TASK_ASSIGNED,
    EventType.SELECTION_DECISION,
    EventType.TASK_STARTED,
    EventType.TASK_COMPLETED,
    EventType.TASK_FAILED,
    EventType.FILE_MODIFIED,
    EventType.FAILURE,
    EventType.TASK_BLOCKED,
    EventType.TASK_DEPENDENCY_ADDED,
    EventType.TASK_PRIORITY_CHANGED,
    EventType.HANDOFF_CREATED,
    EventType.SUBTASK_CREATED,
    EventType.SUBTASK_STARTED,
    EventType.SUBTASK_COMPLETED,
    EventType.SUBTASK_FAILED,
    EventType.WORKFLOW_CREATED,
    EventType.WORKFLOW_STARTED,
    EventType.WORKFLOW_COMPLETED,
    EventType.WORKFLOW_FAILED,
    EventType.RESULT_AGGREGATED,
    EventType.WORKFLOW_STATE_CHANGED,
    EventType.RETRY_SCHEDULED,
    EventType.AGENT_REGISTERED,
    EventType.AGENT_HEALTH_CHANGED,
    EventType.AGENT_EXECUTION_STARTED,
    EventType.AGENT_EXECUTION_COMPLETED,
    EventType.AGENT_EXECUTION_FAILED,
    EventType.COST_CEILING_EXCEEDED,
    EventType.CAPABILITY_UPDATED,
    EventType.QUEUE_ITEM_ENQUEUED,
    EventType.QUEUE_ITEM_DEQUEUED,
    EventType.WORKER_STARTED,
    EventType.WORKER_STOPPED,
    EventType.DUPLICATE_DETECTED,
    EventType.IDEMPOTENCY_KEY_RECORDED,
    EventType.LEASE_ACQUIRED,
    EventType.LEASE_RENEWED,
    EventType.LEASE_RELEASED,
    EventType.LEASE_EXPIRED,
    EventType.TASK_REQUEUED,
    EventType.WORKER_HEARTBEAT,
    EventType.WORKER_STALE,
    EventType.RECOVERY_STARTED,
    EventType.RECOVERY_COMPLETED,
    EventType.RECOVERY_FAILED,
    EventType.RESOURCE_CLOSED,
    EventType.SNAPSHOT_RESTORED,
    EventType.CLUSTER_NODE_REGISTERED,
    EventType.WORKER_REGISTERED,
    EventType.QUEUE_BACKEND_OUTAGE,
    EventType.CIRCUIT_BREAKER_OPENED,
    EventType.CIRCUIT_BREAKER_HALF_OPENED,
    EventType.CIRCUIT_BREAKER_CLOSED,
    EventType.RETRY_ATTEMPTED,
    EventType.BULKHEAD_REJECTED,
    EventType.TEAM_CREATED,
    EventType.COLLABORATION_STARTED,
    EventType.COLLABORATION_COMPLETED,
    EventType.COLLABORATION_FAILED,
    EventType.DELEGATION_CREATED,
    EventType.DELEGATION_COMPLETED,
    EventType.DELEGATION_FAILED,
    EventType.NEGOTIATION_STARTED,
    EventType.NEGOTIATION_COMPLETED,
    EventType.NEGOTIATION_TIMEOUT,
    EventType.PROPOSAL_CREATED,
    EventType.PROPOSAL_ACCEPTED,
    EventType.PROPOSAL_REJECTED,
    EventType.VOTE_CAST,
    EventType.CONSENSUS_REACHED,
    EventType.CONSENSUS_FAILED,
    EventType.SUPERVISOR_INTERVENTION,
    EventType.LEARNING_CYCLE_STARTED,
    EventType.LEARNING_CYCLE_COMPLETED,
    EventType.RECOMMENDATION_GENERATED,
    EventType.RECOMMENDATION_APPLIED,
    EventType.RECOMMENDATION_REJECTED,
    EventType.POLICY_UPDATE_PROPOSED,
    EventType.POLICY_UPDATE_APPROVED,
    EventType.POLICY_UPDATE_REJECTED,
    EventType.ORGANIZATIONAL_PATTERN_DISCOVERED,
    EventType.GOVERNANCE_REVIEW_INITIATED,
    EventType.GOVERNANCE_ALIGNMENT_EVALUATED,
    EventType.GOVERNANCE_TRAJECTORY_SIMULATED,
    EventType.GOVERNANCE_AUTONOMY_ASSESSED,
    EventType.GOVERNANCE_DECISION_SYNTHESIZED,
    EventType.GOVERNANCE_CONSTRAINTS_APPLIED,
    EventType.GOVERNANCE_SYSTEM_UPDATED,
    EventType.GOVERNANCE_POST_CHECK_COMPLETED,
    EventType.PIPELINE_RUN_STARTED,
    EventType.PIPELINE_STATE_CHANGED,
    EventType.OBJECTIVE_RECEIVED,
    EventType.GOVERNANCE_PRECHECK_COMPLETED,
    EventType.ECONOMIC_EVALUATION_COMPLETED,
    EventType.STRATEGIC_PLAN_CREATED,
    EventType.GOAL_DECOMPOSITION_COMPLETED,
    EventType.EXECUTION_PLAN_CREATED,
    EventType.ARBITRATION_COMPLETED,
    EventType.FINAL_DECISION_RECORDED,
    EventType.SCHEDULER_EXECUTION_STARTED,
    EventType.RUNTIME_FEEDBACK_RECORDED,
    EventType.PREDICTION_ERROR_DETECTED,
    EventType.MODEL_UPDATE_PROPOSED,
    EventType.PIPELINE_RUN_COMPLETED,
    EventType.PIPELINE_RUN_FAILED,
    EventType.WORLD_STATE_OBSERVED,
    EventType.WORLD_SIMULATION_RUN,
    EventType.COUNTERFACTUAL_GENERATED,
    EventType.COUNTERFACTUAL_EVALUATED,
    EventType.COUNTERFACTUAL_RECOMMENDATION,
    EventType.SCENARIO_GENERATED,
    EventType.SCENARIO_EVALUATED,
    EventType.SCENARIO_RECOMMENDED,
    EventType.FORESIGHT_GENERATED,
    EventType.FORESIGHT_EVALUATED,
    EventType.FORESIGHT_RECOMMENDED,
    EventType.META_REASONING_STARTED,
    EventType.META_REASONING_COMPLETED,
    EventType.DECISION_EXPLAINED,
    EventType.UNCERTAINTY_ESTIMATED,
    EventType.KNOWLEDGE_GAP_DETECTED,
    EventType.CONFIDENCE_CALIBRATED,
    EventType.INFORMATION_NEED_DETECTED,
    EventType.INFORMATION_ACTION_SELECTED,
    EventType.INFORMATION_GAIN_ESTIMATED,
    EventType.BELIEF_COMPUTED,
    EventType.CONTRADICTION_DETECTED,
    EventType.BELIEF_REVISED,
    EventType.UNCERTAINTY_COMPUTED,
    EventType.EVIDENCE_RECORDED,
    EventType.EVIDENCE_DECAYED,
    EventType.TRUST_UPDATED,
    EventType.CALIBRATION_UPDATED,
    EventType.BELIEF_DRIFT_DETECTED,
    EventType.AGENT_REPUTATION_UPDATED,
    EventType.AGENT_VOTE_CAST,
    EventType.AGENT_CONSENSUS_REACHED,
    EventType.AGENT_ARBITRATION_DECISION,
    EventType.TOOL_EXECUTION_STARTED,
    EventType.TOOL_EXECUTION_COMPLETED,
    EventType.AGENT_RUNTIME_UPDATED,
    EventType.AGENT_SELECTION_REQUESTED,
    EventType.AGENT_SELECTION_SCORED,
    EventType.AGENT_SELECTED,
    EventType.AGENT_CAPABILITY_REGISTERED,
    EventType.TASK_CLASSIFIED,
    EventType.CAPABILITY_MATCHED,
    EventType.AGENT_CAPABILITY_OBSERVED,
    EventType.AGENT_CAPABILITY_LEARNED,
    EventType.AGENT_CAPABILITY_DECAYED,
    EventType.AGENT_CAPABILITY_DRIFT_DETECTED,
    EventType.AGENT_CAPABILITY_TREND_UPDATED,
    EventType.AGENT_CAPABILITY_FORECAST_UPDATED,
    EventType.AGENT_COUNTERFACTUAL_RUN,
    EventType.AGENT_CAUSAL_IMPACT_RECORDED,
    EventType.FUSION_COMPUTED,
    EventType.SIGNAL_CALIBRATED,
    EventType.DECISION_COMPUTED,
    EventType.POLICY_EVALUATED,
    EventType.POLICY_UPDATED,
    EventType.POLICY_DIVERGENCE_DETECTED,
    EventType.SIGNAL_CREDIT_ASSIGNED,
    EventType.SIGNAL_ATTRIBUTION_UPDATED,
    EventType.SIGNAL_IMPORTANCE_CHANGED,
    EventType.ATTENTION_ALLOCATED,
    EventType.RESOURCE_BUDGET_UPDATED,
    EventType.ATTENTION_REALLOCATED,
    EventType.WORKSPACE_UPDATED,
    EventType.WORKSPACE_ITEM_ADDED,
    EventType.WORKSPACE_ITEM_REMOVED,
    EventType.EPISODE_CREATED,
    EventType.EPISODE_RETRIEVED,
    EventType.EPISODE_FORGOTTEN,
    EventType.SEMANTIC_CONCEPT_CREATED,
    EventType.SEMANTIC_CONCEPT_UPDATED,
    EventType.SEMANTIC_CONCEPT_FORGOTTEN,
}



