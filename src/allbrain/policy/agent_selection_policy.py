from __future__ import annotations

from typing import Any

from allbrain.memory import MemoryRetriever


class AgentSelectionPolicy:
    def recommend(
        self,
        *,
        task: dict[str, Any],
        metrics: dict[str, dict[str, Any]],
        advanced_metrics: dict[str, Any],
        memory: MemoryRetriever,
    ) -> dict[str, Any]:
        query = " ".join(str(task.get(key, "")) for key in ["goal", "kind", "domain"])
        similar = memory.retrieve_similar_workflows(query, top_k=3)
        failure_patterns = memory.retrieve_failure_patterns(query, top_k=3)
        agents = sorted(set(metrics) | set(advanced_metrics.get("agents", {})))
        scored = [
            self._score_agent(agent_id, metrics=metrics, advanced_metrics=advanced_metrics, similar=similar)
            for agent_id in agents
        ]
        scored.sort(key=lambda item: (-item["score"], item["agent_id"]))
        recommended = scored[0] if scored else {"agent_id": None, "score": 0.0, "reasoning": []}
        confidence = float(recommended["score"])
        return {
            "recommended_agent": recommended["agent_id"],
            "confidence": round(confidence, 6),
            "confidence_level": "low" if confidence < 0.4 else "medium" if confidence < 0.7 else "high",
            "fallback_chain": [item["agent_id"] for item in scored[1:4] if item["agent_id"]],
            "reasoning": recommended["reasoning"],
            "candidate_agents": scored,
            "memory": {
                "similar_workflows": similar,
                "failure_patterns": failure_patterns,
            },
        }

    def _score_agent(
        self,
        agent_id: str,
        *,
        metrics: dict[str, dict[str, Any]],
        advanced_metrics: dict[str, Any],
        similar: list[dict[str, object]],
    ) -> dict[str, Any]:
        perf = metrics.get(agent_id, {})
        adv = advanced_metrics.get("agents", {}).get(agent_id, {})
        success_rate = float(perf.get("success_rate", 0.0) or 0.0)
        confidence = float(perf.get("confidence", 0.0) or 0.0)
        latency_score = max(0.0, min(1.0, 1 - float(adv.get("p95_latency_ms", 0) or 0) / 10_000))
        cost_score = max(0.0, min(1.0, 1 - float(adv.get("cost_per_success", 0.0) or 0.0)))
        memory_bonus = 0.1 if any(item.get("tags", {}).get("agent") == agent_id for item in similar) else 0.0
        score = round(
            success_rate * 0.4 + confidence * 0.2 + latency_score * 0.15 + cost_score * 0.15 + memory_bonus, 6
        )
        return {
            "agent_id": agent_id,
            "score": score,
            "reasoning": [
                f"success_rate={success_rate:.3f}",
                f"confidence={confidence:.3f}",
                f"latency_score={latency_score:.3f}",
                f"cost_score={cost_score:.3f}",
                f"memory_bonus={memory_bonus:.3f}",
            ],
        }
