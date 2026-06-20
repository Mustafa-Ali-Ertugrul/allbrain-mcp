from __future__ import annotations

from typing import Any

from allbrain.workflow.models import AggregatedResult, AggregationStrategy, SubtaskResult


class ResultAggregator:
    def aggregate(
        self,
        *,
        parent_task_id: str,
        subtask_results: list[SubtaskResult],
        strategy: AggregationStrategy = AggregationStrategy.CONCAT,
    ) -> AggregatedResult:
        if not subtask_results:
            return AggregatedResult(
                task_id=parent_task_id,
                strategy=strategy,
                outputs=[],
                merged_artifacts=[],
                conflicts=[],
                metadata={"count": 0},
            )

        if strategy == AggregationStrategy.CONCAT:
            return self._concat(parent_task_id, subtask_results)
        if strategy == AggregationStrategy.MERGE:
            return self._merge(parent_task_id, subtask_results)
        if strategy == AggregationStrategy.VOTE:
            return self._vote(parent_task_id, subtask_results)
        if strategy == AggregationStrategy.SUMMARY:
            return self._summary(parent_task_id, subtask_results)
        return self._concat(parent_task_id, subtask_results)

    def _concat(self, task_id: str, results: list[SubtaskResult]) -> AggregatedResult:
        outputs = [r.output for r in results if r.output]
        artifacts: list[str] = []
        seen = set()
        for r in results:
            for a in r.artifacts:
                if a not in seen:
                    artifacts.append(a)
                    seen.add(a)
        return AggregatedResult(
            task_id=task_id,
            strategy=AggregationStrategy.CONCAT,
            outputs=outputs,
            merged_artifacts=artifacts,
            conflicts=[],
            metadata={"count": len(results), "agents": list({r.agent_id for r in results if r.agent_id})},
        )

    def _merge(self, task_id: str, results: list[SubtaskResult]) -> AggregatedResult:
        outputs: list[str] = []
        merged: dict[str, Any] = {}
        conflicts: list[dict[str, Any]] = []
        for r in results:
            if r.output:
                outputs.append(r.output)
            for key, value in r.metadata.items():
                if key in merged and merged[key] != value:
                    conflicts.append({
                        "key": key,
                        "values": [merged[key], value],
                        "agents": list({merged.get("__agent"), r.agent_id}),
                    })
                merged[key] = value
                merged["__agent"] = r.agent_id
        merged.pop("__agent", None)
        artifacts: list[str] = []
        seen = set()
        for r in results:
            for a in r.artifacts:
                if a not in seen:
                    artifacts.append(a)
                    seen.add(a)
        return AggregatedResult(
            task_id=task_id,
            strategy=AggregationStrategy.MERGE,
            outputs=outputs,
            merged_artifacts=artifacts,
            conflicts=conflicts,
            metadata=merged | {"count": len(results)},
        )

    def _vote(self, task_id: str, results: list[SubtaskResult]) -> AggregatedResult:
        if not results:
            return AggregatedResult(
                task_id=task_id,
                strategy=AggregationStrategy.VOTE,
                outputs=[],
                merged_artifacts=[],
                conflicts=[],
                metadata={"count": 0},
            )
        outputs = [r.output for r in results if r.output]
        if not outputs:
            return AggregatedResult(
                task_id=task_id,
                strategy=AggregationStrategy.VOTE,
                outputs=[],
                merged_artifacts=[],
                conflicts=[],
                metadata={"count": len(results)},
            )
        from collections import Counter

        counter = Counter(outputs)
        winner, count = counter.most_common(1)[0]
        total = len(outputs)
        return AggregatedResult(
            task_id=task_id,
            strategy=AggregationStrategy.VOTE,
            outputs=[winner],
            merged_artifacts=[],
            conflicts=[
                {
                    "output": o,
                    "count": c,
                    "agents": [r.agent_id for r in results if r.output == o and r.agent_id],
                }
                for o, c in counter.items()
                if o != winner
            ],
            metadata={
                "count": len(results),
                "winner": winner,
                "winner_count": count,
                "total_votes": total,
                "agreement_rate": round(count / total, 4) if total else 0,
            },
        )

    def _summary(self, task_id: str, results: list[SubtaskResult]) -> AggregatedResult:
        outputs = [r.output for r in results if r.output]
        concatenated = "\n\n---\n\n".join(outputs)
        return AggregatedResult(
            task_id=task_id,
            strategy=AggregationStrategy.SUMMARY,
            outputs=[concatenated],
            merged_artifacts=[],
            conflicts=[],
            metadata={
                "count": len(results),
                "note": "SUMMARY strategy returns concatenated output; LLM summarization is a future enhancement",
            },
        )
