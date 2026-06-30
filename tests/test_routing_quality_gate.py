from __future__ import annotations

import re
from pathlib import Path

FILES = ["scorer.py", "reducer.py", "manager.py", "events.py", "model.py"]


def _no_nondet(d, f):
    c = (Path(d) / f).read_text(encoding="utf-8")
    for t in ("uuid7", "datetime.now", "random.", "time.time"):
        assert t not in c, repr(d + "/" + f) + " uses " + repr(t)


class TestQualityGate:
    def test_no_nondeterminism(self):
        for f in FILES:
            _no_nondet("src/allbrain/routing", f)

    def test_does_not_change_confidence(self):
        from allbrain.events.schemas import EventType
        from allbrain.revision import RevisionManager
        from allbrain.revision import make_payload as mr
        from allbrain.routing.events import make_selected_payload

        class E:
            def __init__(self, t, i, p):
                self.type = t; self.id = i; self.payload = p

        base = [E(EventType.BELIEF_REVISED.value, "1", mr(context_key="default", old_confidence=0.9, new_confidence=0.6, reason="contradiction", evidence_count=0))]
        w = list(base) + [E(EventType.AGENT_SELECTED.value, "2", make_selected_payload(task_id="t", task_type="x", agent_id="a", selection_score=0.7))]
        mgr = RevisionManager()
        assert mgr.query(base).confidence == mgr.query(w).confidence
        assert mgr.query(w).selected_agent_score == 0.7

    def test_no_recompute(self):
        c = Path("src/allbrain/revision/manager.py").read_text(encoding="utf-8")
        lines = c.splitlines()
        inh = False
        forb = [r"\bRoutingManager\(", r"\bRoutingReducer\("]
        for n, l in enumerate(lines, 1):
            s = l.strip()
            if s.startswith("def _read_selected_agent_score"):
                inh = True; continue
            if inh and (s.startswith("def ") or s.startswith("class ") or s.startswith("@")):
                inh = False
            if inh:
                continue
            for p in forb:
                assert not re.search(p, l), "revision/manager.py:" + str(n) + " contains " + repr(p)
