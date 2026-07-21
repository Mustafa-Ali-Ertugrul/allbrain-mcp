from __future__ import annotations

import re
from pathlib import Path

import pytest

REPUTATION_FILES = [
    "estimator.py",
    "reducer.py",
    "manager.py",
    "events.py",
    "model.py",
]


def _assert_no_nondeterminism_tokens(relative_dir: str, filename: str) -> None:
    path = Path(relative_dir) / filename
    content = path.read_text(encoding="utf-8")
    for token in ("uuid7", "datetime.now", "random.", "time.time"):
        assert token not in content, f"{relative_dir}/{filename} uses {token!r} — must be deterministic hash only"


class TestQualityGate:
    def test_reputation_module_no_nondeterminism(self):
        """Sprint 48 quality gate: reputation/*.py must be deterministic.

        No uuid7(), datetime.now(), random.*, or time.time() in:
          - estimator.py (pure math)
          - reducer.py (event-log replay)
          - manager.py (event-log projection)
          - events.py (payload validation/creation)
          - model.py (frozen dataclass)
        """
        for filename in REPUTATION_FILES:
            _assert_no_nondeterminism_tokens("src/allbrain/domains/collaboration/reputation", filename)

    def test_reputation_does_not_change_confidence(self):
        """Sprint 48 contract: reputation is metadata only.

        With the SAME event log, RevisionState.confidence is byte-equal before
        and after an AGENT_REPUTATION_UPDATED event is added. Reputation may
        change agent_reputation — but it MUST NOT modify the `confidence` field,
        which is the Sprint 46 contract.
        """
        from allbrain.domains.collaboration.reputation.events import make_payload as make_reputation_payload
        from allbrain.domains.memory.revision import RevisionManager
        from allbrain.domains.memory.revision import make_payload as make_revision_payload
        from allbrain.events.schemas import EventType

        class E:
            def __init__(self, t, i, p):
                self.type = t
                self.id = i
                self.payload = p

        base_events = [
            E(
                EventType.BELIEF_REVISED.value,
                "1",
                make_revision_payload(
                    context_key="default",
                    old_confidence=0.90,
                    new_confidence=0.60,
                    reason="contradiction",
                    evidence_count=0,
                ),
            ),
            E(EventType.TRUST_UPDATED.value, "2", {"context_key": "default", "trust_score": 0.8}),
        ]

        with_reputation = list(base_events) + [
            E(
                EventType.AGENT_REPUTATION_UPDATED.value,
                "3",
                make_reputation_payload(
                    agent_id="a",
                    task_id="t",
                    success=True,
                    confidence=0.5,
                    duration_ms=0,
                    retry_count=0,
                    reputation_score=0.85,
                    analysis_id="x",
                ),
            ),
        ]

        manager = RevisionManager()
        state_before = manager.query(base_events)
        state_after = manager.query(with_reputation)

        assert state_after.confidence == state_before.confidence
        assert state_after.agent_reputation != 1.0

    def test_revision_manager_reads_reputation_from_event_log_only(self):
        """Zorunlu: revision's agent_reputation comes from the event log, not
        recomputed. The only allowed runtime reference to reputation is the
        module-level import of pure-math helpers.
        """
        manager_path = Path("src/allbrain/domains/memory/revision/manager.py")
        content = manager_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        in_helper = False
        forbidden = [
            r"\bReputationManager\(",
            r"\bReputationReducer\(",
        ]
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("def _read_agent_reputation"):
                in_helper = True
                continue
            if in_helper and (stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("@")):
                in_helper = False
            if in_helper:
                continue
            for pattern in forbidden:
                assert not re.search(pattern, line), (
                    f"revision/manager.py:{line_no} contains {pattern!r} — "
                    "Zorunlu: agent_reputation must come from the event log, not recompute."
                )
