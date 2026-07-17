"""Queue item payloads are redacted before persistence."""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import select

from allbrain.models.entities import QueueItemRecord
from allbrain.server.queueing import QueueCoordinator
from allbrain.storage.database import open_session
from tests._helpers import make_context


def test_enqueue_task_redacts_secret_fields(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    coord = QueueCoordinator(context)
    coord.enqueue_task(
        task_id="t-secret",
        goal="goal",
        kind="testing",
        priority=2,
        agent_id="codex",
        workflow_id="wf-1",
        metadata={"api_key": "super-secret-value", "note": "ok"},
        idempotency_prefix="test",
    )
    with open_session(context.repository.engine) as db:
        record = db.exec(select(QueueItemRecord).where(QueueItemRecord.task_id == "t-secret")).first()
        assert record is not None
        payload = json.loads(record.payload_json)
    text = json.dumps(payload)
    assert "super-secret-value" not in text
    assert "********" in text
