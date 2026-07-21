from __future__ import annotations

import re
from pathlib import Path

ARBITRATION_FILES = [
    "scorer.py",
    "reducer.py",
    "manager.py",
    "events.py",
    "model.py",
]


def _assert_no_nondeterminism(relative_dir, filename):
    path = Path(relative_dir) / filename
    content = path.read_text(encoding="utf-8")
    for token in ("uuid7", "datetime.now", "random.", "time.time"):
        assert token not in content, (
            repr(relative_dir + "/" + filename) + " uses " + repr(token) + " -- must be deterministic hash only"
        )


class TestQualityGate:
    def test_no_nondeterminism(self):
        for f in ARBITRATION_FILES:
            _assert_no_nondeterminism("src/allbrain/domains/collaboration/arbitration", f)

    def test_does_not_change_confidence(self):
        from allbrain.domains.collaboration.arbitration.events import make_consensus_payload
        from allbrain.domains.memory.revision import RevisionManager
        from allbrain.domains.memory.revision import make_payload as make_rev_payload
        from allbrain.events.schemas import EventType

        class E:
            def __init__(self, t, i, p):
                self.type = t
                self.id = i
                self.payload = p

        base = [
            E(
                EventType.BELIEF_REVISED.value,
                "1",
                make_rev_payload(
                    context_key="default",
                    old_confidence=0.9,
                    new_confidence=0.6,
                    reason="contradiction",
                    evidence_count=0,
                ),
            ),
        ]
        with_consensus = list(base) + [
            E(
                EventType.AGENT_CONSENSUS_REACHED.value,
                "2",
                make_consensus_payload(
                    context_key="default", winner_candidate="c", score=0.5, agreement_ratio=1.0, method="weighted"
                ),
            ),
        ]
        manager = RevisionManager()
        s_before = manager.query(base)
        s_after = manager.query(with_consensus)
        assert s_after.confidence == s_before.confidence
        assert s_after.consensus_score == 0.5

    def test_no_recompute(self):
        path = Path("src/allbrain/domains/memory/revision/manager.py")
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        in_helper = False
        forbidden = [r"\bArbitrationManager\(", r"\bArbitrationReducer\("]
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("def _read_consensus_score"):
                in_helper = True
                continue
            if in_helper and (stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("@")):
                in_helper = False
            if in_helper:
                continue
            for pattern in forbidden:
                assert not re.search(pattern, line), (
                    "revision/manager.py:"
                    + str(line_no)
                    + " contains "
                    + repr(pattern)
                    + " -- Zorunlu: consensus must come from event log, not recompute."
                )
