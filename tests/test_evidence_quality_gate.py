from __future__ import annotations

from pathlib import Path

import pytest


def test_evidence_quality_gate_no_uuid7_or_now_or_random_or_time_in_determinism_path():
    """Sprint 46 quality gate: estimator.py, reducer.py, manager.py, decay.py,
    trust.py must not use uuid7(), datetime.now(), random.*, or time.time()
    — deterministic hash only.

    The pipeline write-path (pipeline.py _evidence_step / _trust_step) is
    exempt because it runs at runtime, not replay.
    """
    determinism_critical = [
        "estimator.py",
        "reducer.py",
        "manager.py",
        "decay.py",
        "trust.py",
    ]
    base = Path("src/allbrain/domains/analysis/evidence")
    if not base.exists():
        base = Path("src/allbrain/evidence")
    for filename in determinism_critical:
        content = (base / filename).read_text(encoding="utf-8")
        assert "uuid7" not in content, f"evidence/{filename} uses uuid7 — must be deterministic hash"
        assert "datetime.now" not in content, f"evidence/{filename} uses datetime.now — must be deterministic"
        assert "random." not in content, f"evidence/{filename} uses random — must be deterministic"
        assert "time.time" not in content, f"evidence/{filename} uses time.time — must be deterministic"


def test_revision_trust_uses_event_log_only():
    """Zorunlu: revision's trust_score is read from the event log, not
    recomputed from beliefs/contradictions. The _read_trust_score helper
    in revision/manager.py MUST NOT call evidence_weight, trust_score,
    decay, or any derivation function from allbrain.domains.analysis.evidence.

    Uses word-boundary regex to avoid matching function NAMES like
    `_read_trust_score` (which is just a helper name, not a call).
    """
    import re

    manager_path = Path("src/allbrain/domains/memory/revision/manager.py")
    content = manager_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    in_helper = False
    for forbidden in [
        r"\bevidence_weight\(",
        r"\btrust_score\(",
        r"\bdecay\(",
        r"from\s+allbrain\.evidence",
        r"\bcomposite_uncertainty\(",
    ]:
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("def _read_trust_score"):
                in_helper = True
                continue
            if in_helper and (stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("@")):
                in_helper = False
            if in_helper:
                continue
            assert not re.search(forbidden, line), (
                f"revision/manager.py:{line_no} contains {forbidden!r} — "
                "Zorunlu: trust_score must come from the event log, not recompute."
            )
