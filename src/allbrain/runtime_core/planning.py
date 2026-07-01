from __future__ import annotations

from typing import Any

from allbrain.runtime_core.contracts import EconomicEvaluation, ObjectiveContext, StrategicPlan


class StrategicPlanningBridge:
    engine_id = "deterministic-strategy-v1"

    def plan(self, objective: ObjectiveContext, economic: EconomicEvaluation) -> StrategicPlan:
        objective_id = objective.objective_id or objective.task_id or "objective"
        return StrategicPlan(
            plan_id=f"plan:{objective_id}",
            objective_id=objective_id,
            goal=objective.goal or objective.title or objective_id,
            decision="activate" if economic.decision == "invest" else "research",
            priority=objective.priority,
            confidence=objective.confidence,
            engine_id=self.engine_id,
        )


class GoalDecompositionBridge:
    def decompose(self, objective: dict[str, Any], plan: dict[str, Any], economic: dict[str, Any]) -> dict[str, Any]:
        task_id = str(objective.get("task_id") or plan["objective_id"])
        kind = str(objective.get("kind", "implementation"))
        subtasks = [
            {
                "node_id": f"{task_id}:main",
                "task_id": task_id,
                "goal": plan["goal"],
                "kind": kind,
                "priority": plan["priority"],
            }
        ]
        edges: list[dict[str, str]] = []
        if economic["risk_level"] in {"high", "critical"}:
            subtasks.append(
                {
                    "node_id": f"{task_id}:review",
                    "task_id": task_id,
                    "goal": f"Review {plan['goal']}",
                    "kind": "review",
                    "priority": 5,
                }
            )
            edges.append({"from": f"{task_id}:main", "to": f"{task_id}:review", "edge_type": "depends_on"})
        if kind == "implementation":
            subtasks.append(
                {
                    "node_id": f"{task_id}:tests",
                    "task_id": task_id,
                    "goal": f"Test {plan['goal']}",
                    "kind": "testing",
                    "priority": max(3, plan["priority"]),
                }
            )
            edges.append({"from": f"{task_id}:main", "to": f"{task_id}:tests", "edge_type": "depends_on"})
        return {"task_id": task_id, "subtasks": subtasks, "edges": edges}
