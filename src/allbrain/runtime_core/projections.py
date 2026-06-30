from __future__ import annotations

from collections import Counter
from typing import Any

from allbrain.foundations import canonical_event_sort
from allbrain.models.schemas import EventRead


class RuntimeCoreStateBuilder:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        runs: dict[str, dict[str, Any]] = {}
        for event in canonical_event_sort(events):
            run_id = event.payload.get("run_id")
            if not isinstance(run_id, str):
                continue
            run = runs.setdefault(run_id, {"run_id": run_id, "status": "INIT", "events": []})
            run["events"].append(event.id)
            if event.type == "pipeline_run_started":
                run["status"] = "INIT"
                run["execute_mode"] = event.payload.get("execute_mode")
            elif event.type == "pipeline_state_changed":
                run["status"] = event.payload.get("new_status", run["status"])
            elif event.type == "objective_received":
                run["objective"] = event.payload.get("objective")
            elif event.type == "governance_precheck_completed":
                run["governance"] = event.payload
            elif event.type == "economic_evaluation_completed":
                run["economic"] = event.payload
            elif event.type == "strategic_plan_created":
                run["strategic_plan"] = event.payload
            elif event.type == "goal_decomposition_completed":
                run["decomposition"] = event.payload
            elif event.type == "execution_plan_created":
                run["execution_plan"] = event.payload
            elif event.type == "arbitration_completed":
                run["arbitration"] = event.payload
            elif event.type == "final_decision_recorded":
                run["final_decision"] = event.payload
            elif event.type == "scheduler_execution_started":
                run["scheduler"] = event.payload
            elif event.type == "runtime_feedback_recorded":
                run["feedback"] = event.payload
            elif event.type == "prediction_error_detected":
                run.setdefault("prediction_errors", []).append(event.payload)
            elif event.type == "model_update_proposed":
                run.setdefault("model_update_proposals", []).append(event.payload)
            elif event.type == "pipeline_run_completed":
                run["status"] = event.payload.get("status", run["status"])
            elif event.type == "pipeline_run_failed":
                run["status"] = "FAILED"
                run["error"] = event.payload.get("error")
        return {"runs": runs, "run_count": len(runs)}


class RuntimeCoreMetrics:
    def build(self, events: list[EventRead]) -> dict[str, Any]:
        state = RuntimeCoreStateBuilder().build(events)
        runs = list(state["runs"].values())
        total = max(1, len(runs))
        counts = Counter(str(run.get("status", "UNKNOWN")) for run in runs)
        confidences = [
            float(run.get("final_decision", {}).get("confidence"))
            for run in runs
            if isinstance(run.get("final_decision", {}).get("confidence"), int | float)
        ]
        feedback_count = sum(1 for run in runs if run.get("feedback"))
        prediction_error_count = sum(len(run.get("prediction_errors", [])) for run in runs)
        model_update_count = sum(len(run.get("model_update_proposals", [])) for run in runs)
        return {
            "pipeline_completion_ratio": round(counts["COMPLETED"] / total, 6),
            "blocked_ratio": round(counts["BLOCKED"] / total, 6),
            "mean_decision_confidence": round(sum(confidences) / len(confidences), 6) if confidences else 0.0,
            "prediction_error_count": prediction_error_count,
            "model_update_proposal_count": model_update_count,
            "feedback_loop_completion_ratio": round(feedback_count / total, 6),
            "run_count": len(runs),
            "status_counts": dict(sorted(counts.items())),
        }
