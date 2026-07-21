from __future__ import annotations

import re
from pathlib import Path

FS = ["scorer.py", "reducer.py", "manager.py", "events.py", "model.py"]


def _n(d, f):
    p = Path(d) / f
    if not p.exists():
        p = Path(d.replace("src/allbrain/", "src/allbrain/domains/learning/")) / f
    c = p.read_text(encoding="utf-8")
    for t in ("uuid7", "datetime.now", "random.", "time.time"):
        assert t not in c, repr(d + "/" + f) + " uses " + repr(t)


class TestQualityGate:
    def test_no_nondeterminism(self):
        for f in FS:
            _n("src/allbrain/capabilities", f)

    def test_does_not_change_confidence(self):
        from allbrain.capabilities.events import make_matched_payload
        from allbrain.events.schemas import EventType
        from allbrain.revision import RevisionManager
        from allbrain.revision import make_payload as mr

        class E:
            def __init__(self, t, i, p):
                self.type = t
                self.id = i
                self.payload = p

        base = [
            E(
                EventType.BELIEF_REVISED.value,
                "1",
                mr(
                    context_key="default",
                    old_confidence=0.9,
                    new_confidence=0.6,
                    reason="contradiction",
                    evidence_count=0,
                ),
            )
        ]
        w = list(base) + [
            E(
                EventType.CAPABILITY_MATCHED.value,
                "2",
                make_matched_payload(agent_id="a", task_type="x", match_score=0.5, match_kind="partial"),
            )
        ]
        mgr = RevisionManager()
        assert mgr.query(base).confidence == mgr.query(w).confidence
        assert mgr.query(w).capability_score == 0.5

    def test_no_recompute(self):
        c = Path("src/allbrain/domains/memory/revision/manager.py").read_text(encoding="utf-8")
        ls = c.splitlines()
        inh = False
        forb = [r"\bCapabilityManager\(", r"\bCapabilityReducer\("]
        for n, line in enumerate(ls, 1):
            s = line.strip()
            if s.startswith("def _read_capability_score"):
                inh = True
                continue
            if inh and (s.startswith("def ") or s.startswith("class ") or s.startswith("@")):
                inh = False
            if inh:
                continue
            for p in forb:
                assert not re.search(p, line), "revision/manager.py:" + str(n) + " contains " + repr(p)

    def test_selection_score_unchanged(self):
        from allbrain.routing.scorer import extended_selection_score, selection_score

        s1 = selection_score(reputation=0.5, runtime_score=0.5, calibrated_trust=0.5, consensus_score=0.5)
        s2 = extended_selection_score(
            reputation=0.5, runtime_score=0.5, calibrated_trust=0.5, consensus_score=0.5, capability_match=0.5
        )
        assert s1 != s2
