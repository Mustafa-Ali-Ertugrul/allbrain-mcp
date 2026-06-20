from __future__ import annotations

from allbrain.agents.queue import QueueItem
from allbrain.reliability import Deduplicator, IdempotencyKeyBuilder
from allbrain.workflow.models import TaskNode


def test_idempotency_keys_are_stable() -> None:
    builder = IdempotencyKeyBuilder()
    item = QueueItem(node=TaskNode(node_id="n1", task_id="t1", goal="Do thing"), agent_id="builder", workflow_id="wf1")

    assert builder.workflow_key("wf1") == builder.workflow_key("wf1")
    assert builder.task_key("t1", "n1") == builder.task_key("t1", "n1")
    assert builder.queue_item_key(item) == builder.queue_item_key(item)


def test_deduplicator_detects_duplicate_task_workflow_and_queue_item() -> None:
    dedup = Deduplicator()
    item = QueueItem(node=TaskNode(node_id="n1", task_id="t1", goal="Do thing"), agent_id="builder", workflow_id="wf1")

    assert not dedup.workflow_execution("wf1").duplicate
    assert dedup.workflow_execution("wf1").duplicate
    assert not dedup.task_execution("t1", "n1").duplicate
    assert dedup.task_execution("t1", "n1").duplicate
    assert not dedup.queue_item(item).duplicate
    assert dedup.queue_item(item).duplicate
