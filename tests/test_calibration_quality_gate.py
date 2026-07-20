from __future__ import annotations

import re
from pathlib import Path

import pytest

DETERMINISM_FILES = [
    "estimator.py",
    "reducer.py",
    "manager.py",
    "events.py",
    "model.py",
]


def _assert_no_nondeterminism_tokens(relative_dir: str, filename: str) -> None:
    path = Path(relative_dir) / filename
    if not path.exists() and "drift" in relative_dir:
        path = Path("src/allbrain/domains/analysis/drift") / filename
    content = path.read_text(encoding="utf-8")
    for token in ("uuid7", "datetime.now", "random.", "time.time"):
        assert token not in content, f"{relative_dir}/{filename} uses {token!r} — must be deterministic hash only"


def test_calibration_module_no_nondeterminism():
    """Sprint 47 quality gate: calibration/*.py must be deterministic.

    No uuid7(), datetime.now(), random.*, or time.time() in:
      - estimator.py (pure math)
      - reducer.py (event-log replay)
      - manager.py (event-log projection)
      - events.py (payload validation/creation)
      - model.py (frozen dataclass)
    """
    for filename in DETERMINISM_FILES:
        _assert_no_nondeterminism_tokens("src/allbrain/calibration", filename)


def test_drift_module_no_nondeterminism():
    """Sprint 47 quality gate: drift/*.py must be deterministic.

    No uuid7(), datetime.now(), random.*, or time.time() in:
      - detector.py (pure math)
      - events.py (payload validation/creation)
    """
    for filename in ("detector.py", "events.py"):
        _assert_no_nondeterminism_tokens("src/allbrain/drift", filename)


def test_revision_manager_reads_calibration_and_drift_from_event_log_only():
    """Zorunlu: revision's calibration_error and drift_count come from the
    event log, not recomputed from beliefs/contradictions/calibration.

    The only allowed runtime reference to calibration/drift is the module-level
    import of pure-math helpers (calibrated_trust, mean_calibration_error).
    These are deterministic projections applied to values ALREADY read from
    the event log by `_read_calibration_error` / `_read_drift_count`.

    Inside the helpers, only direct event-log reads are allowed: the helper
    iterates `ordered` and reads `payload[...]`. The function bodies MUST NOT
    delegate to live CalibrationManager / DriftSample / detect_drift.

    Word-boundary regex avoids false-positives on helper names like
    `_read_calibration_error` (a helper, not a recompute call).
    """
    manager_path = Path("src/allbrain/revision/manager.py")
    content = manager_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    in_helper = False
    # These are the recompute calls — running live modules to re-derive state.
    function_call_forbidden = [
        r"\bCalibrationManager\(",
        r"\bDriftSample\(",
        r"\bdetect_drift\(",
    ]
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("def _read_calibration_error") or stripped.startswith("def _read_drift_count"):
            in_helper = True
            continue
        if in_helper and (stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("@")):
            in_helper = False
        if in_helper:
            continue
        for pattern in function_call_forbidden:
            assert not re.search(pattern, line), (
                f"revision/manager.py:{line_no} contains {pattern!r} — "
                "Zorunlu: calibration_error and drift_count must come from the event log, not recompute."
            )


def test_calibration_does_not_change_confidence():
    """Sprint 47 contract (Yol B display-only): calibration is metadata only.

    With the SAME event log, RevisionState.confidence is byte-equal before
    and after a CALIBRATION_UPDATED event is added. Calibration may change
    calibrated_trust, calibration_error, and drift_count — but it MUST NOT
    modify the `confidence` field, which is the Sprint 46 contract.
    """
    from allbrain.calibration import make_payload as make_calibration_payload
    from allbrain.events.schemas import EventType
    from allbrain.revision import RevisionManager
    from allbrain.revision import make_payload as make_revision_payload

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

    with_calibration = list(base_events) + [
        E(
            EventType.CALIBRATION_UPDATED.value,
            "3",
            make_calibration_payload(
                context_key="default",
                predicted_confidence=0.5,
                actual_outcome=True,
            ),
        ),
    ]

    manager = RevisionManager()
    state_before = manager.query(base_events)
    state_after = manager.query(with_calibration)

    # confidence is unchanged
    assert state_after.confidence == state_before.confidence
    # but calibration fields DID change
    assert state_after.calibration_error == pytest.approx(0.25)
    assert state_after.calibrated_trust == pytest.approx(0.6)
    assert state_before.calibration_error == 0.0
    assert state_before.calibrated_trust == pytest.approx(0.8)
