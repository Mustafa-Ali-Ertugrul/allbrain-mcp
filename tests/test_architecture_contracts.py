from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from allbrain.events import EVENT_DOMAINS, EventDomain, EventType, SemanticEventType, event_domain
from allbrain.runtime_core import SystemDecisionPipeline
from allbrain.server.context import BrainContext
from tests.runtime_core.test_system_decision_pipeline import objective
from tests.test_sprint12_memory_policy_ui import events, make_context

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_import_boundaries() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_architecture.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_event_domain_registry_is_exhaustive_and_legacy_semantics_are_stable() -> None:
    assert set(EVENT_DOMAINS) == set(EventType)
    assert len(EVENT_DOMAINS) == 240
    assert len(SemanticEventType) == 224
    assert event_domain(EventType.PIPELINE_RUN_STARTED) is EventDomain.DECISION
    assert event_domain("recovery_started") is EventDomain.RECOVERY
    with pytest.raises(ValueError):
        event_domain("unknown_event")


def test_brain_context_rejects_unknown_keywords_and_infers_agent(tmp_path) -> None:
    existing = make_context(tmp_path)
    inferred = BrainContext(
        repository=existing.repository,
        project_path=existing.project_path,
        active_session=existing.active_session,
    )
    assert inferred.agent_name == existing.active_session.agent_name
    with pytest.raises(TypeError):
        BrainContext(repository=existing.repository, project_path=existing.project_path, typo_attribute=True)


def test_pipeline_failure_event_masks_internal_details(tmp_path) -> None:
    class BrokenStep:
        def execute(self, _state, _services):
            raise RuntimeError("C:/secret/project/database.db")

    context = make_context(tmp_path)
    with pytest.raises(RuntimeError):
        SystemDecisionPipeline(steps=[BrokenStep()]).run(context, objective())

    failure = next(event for event in events(context) if event.type == EventType.PIPELINE_RUN_FAILED.value)
    assert failure.payload["error"] == "Pipeline execution failed"
    assert "secret" not in str(failure.payload)
