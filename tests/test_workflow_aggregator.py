"""Tests for workflow/aggregator.py - ResultAggregator."""

from allbrain.workflow.aggregator import ResultAggregator
from allbrain.workflow.models import AggregationStrategy, SubtaskResult


def _result(
    output: str = "", artifacts: list[str] | None = None, metadata: dict | None = None, agent_id: str | None = None
) -> SubtaskResult:
    return SubtaskResult(
        node_id="t1",
        agent_id=agent_id or "a1",
        output=output,
        artifacts=artifacts or [],
        metadata=metadata or {},
    )


class TestResultAggregator:
    def test_empty_results(self):
        r = ResultAggregator()
        result = r.aggregate(parent_task_id="p1", subtask_results=[])
        assert result.metadata["count"] == 0
        assert result.outputs == []

    def test_concat(self):
        r = ResultAggregator()
        results = [_result("out1", artifacts=["a1"], agent_id="a1"), _result("out2", artifacts=["a2"], agent_id="a2")]
        result = r.aggregate(parent_task_id="p1", subtask_results=results, strategy=AggregationStrategy.CONCAT)
        assert result.outputs == ["out1", "out2"]
        assert result.merged_artifacts == ["a1", "a2"]

    def test_concat_dedup_artifacts(self):
        r = ResultAggregator()
        results = [_result("out1", artifacts=["a1"], agent_id="a1"), _result("out2", artifacts=["a1"], agent_id="a2")]
        result = r.aggregate(parent_task_id="p1", subtask_results=results, strategy=AggregationStrategy.CONCAT)
        assert result.merged_artifacts == ["a1"]

    def test_merge_no_conflict(self):
        r = ResultAggregator()
        results = [
            _result("out1", metadata={"key1": "val1"}, agent_id="a1"),
            _result("out2", metadata={"key2": "val2"}, agent_id="a2"),
        ]
        result = r.aggregate(parent_task_id="p1", subtask_results=results, strategy=AggregationStrategy.MERGE)
        assert len(result.conflicts) == 0
        assert result.metadata["key1"] == "val1"
        assert result.metadata["key2"] == "val2"

    def test_merge_with_conflict(self):
        r = ResultAggregator()
        results = [
            _result("out1", metadata={"key": "val1"}, agent_id="a1"),
            _result("out2", metadata={"key": "val2"}, agent_id="a2"),
        ]
        result = r.aggregate(parent_task_id="p1", subtask_results=results, strategy=AggregationStrategy.MERGE)
        assert len(result.conflicts) == 1
        assert result.conflicts[0]["key"] == "key"

    def test_vote_winner(self):
        r = ResultAggregator()
        results = [_result("A", agent_id="a1"), _result("A", agent_id="a2"), _result("B", agent_id="a3")]
        result = r.aggregate(parent_task_id="p1", subtask_results=results, strategy=AggregationStrategy.VOTE)
        assert result.outputs == ["A"]
        assert result.metadata["winner"] == "A"
        assert result.metadata["winner_count"] == 2

    def test_vote_empty_outputs(self):
        r = ResultAggregator()
        results = [_result("", agent_id="a1"), _result("", agent_id="a2")]
        result = r.aggregate(parent_task_id="p1", subtask_results=results, strategy=AggregationStrategy.VOTE)
        assert result.outputs == []

    def test_summary(self):
        r = ResultAggregator()
        results = [_result("part1", agent_id="a1"), _result("part2", agent_id="a2")]
        result = r.aggregate(parent_task_id="p1", subtask_results=results, strategy=AggregationStrategy.SUMMARY)
        assert "part1" in result.outputs[0]
        assert "part2" in result.outputs[0]

    def test_unknown_strategy_falls_to_concat(self):
        r = ResultAggregator()
        results = [_result("out1", agent_id="a1")]
        result = r.aggregate(parent_task_id="p1", subtask_results=results, strategy="UNKNOWN")
        assert result.outputs == ["out1"]
