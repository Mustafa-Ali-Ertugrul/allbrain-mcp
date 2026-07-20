from __future__ import annotations

from datetime import datetime
from pathlib import Path

from allbrain.domains.analysis.contradiction import (
    CONTRADICTION_TEMPLATE_VERSION,
    INCOMPATIBLE_LIFECYCLE,
    SEVERITY_GOAL_DIVERGENCE,
    SEVERITY_LIFECYCLE_INCOMPATIBLE_SAME_GOAL,
    SEVERITY_LIFECYCLE_INCOMPATIBLE_SHARED,
    ContradictionDetector,
    ContradictionManager,
    ContradictionReducer,
    dedup_contradictions,
)
from allbrain.domains.analysis.contradiction.estimator import (
    _contradiction_key_of,
    _stable_contradiction_id,
)
from allbrain.domains.reasoning.intent.models import Intent
from allbrain.events import EventType
from allbrain.replay import EventReplayEngine


class MockEvent:
    def __init__(self, type, id="", payload=None, created_at=None):
        self.type = type
        self.id = id
        self.payload = payload or {}
        self.created_at = created_at or datetime.now()


def _make_intent(intent_id: str, agent_id: str, goal: str, sub_goal: str, related_files: list[str]) -> Intent:
    return Intent(
        intent_id=intent_id,
        agent_id=agent_id,
        goal=goal,
        sub_goal=sub_goal,
        status="active",
        related_files=related_files,
        confidence=0.8,
        source_event_id=f"evt_{intent_id}",
        created_at=datetime(2020, 1, 1),
    )


def test_contradiction_convergence_no_checkpoint():
    """Zorunlu 1 (honest): when no CONTRADICTION_DETECTED event is in the log,
    both manager and reducer return empty. They do NOT re-derive from intents.

    Before Sprint 43: manager recomputed via the detector and produced
    contradictions from raw intent events, while reducer saw nothing.
    That divergence is now impossible because both views consume only
    the CONTRADICTION_DETECTED stream.
    """
    [
        _make_intent("i1", "codex", "JWT refactor", "task_started", ["auth.py"]),
        _make_intent("i2", "claude", "Auth cleanup", "task_started", ["auth.py"]),
    ]
    events = [
        MockEvent(EventType.TASK_STARTED.value, id="1", payload={"task": "JWT refactor"}),
        MockEvent(EventType.TASK_STARTED.value, id="2", payload={"task": "Auth cleanup"}),
    ]

    manager = ContradictionManager()
    manager_state = manager.query(events)

    reducer = ContradictionReducer()
    for e in events:
        reducer.apply(e)
    reducer_state = reducer.snapshot()

    assert manager_state.contradictions == []
    assert reducer_state.contradictions == []
    assert manager_state.contradictions == reducer_state.contradictions
    assert manager_state.analysis_id == reducer_state.analysis_id


def test_contradiction_convergence_with_checkpoint():
    """Both manager and reducer return the CONTRADICTION_DETECTED payload."""
    detected = MockEvent(
        EventType.CONTRADICTION_DETECTED.value,
        id="10",
        payload={
            "context_key": "default",
            "contradictions": [
                {
                    "severity": "warning",
                    "severity_score": 50,
                    "agents": ["claude", "codex"],
                    "related_files": ["auth.py"],
                    "a_goal": "JWT refactor",
                    "b_goal": "Auth cleanup",
                    "evidence_intent_ids": ["i1", "i2"],
                }
            ],
            "severity_summary": {"warning": 1},
            "evidence_event_ids": ["1", "2"],
            "template_version": CONTRADICTION_TEMPLATE_VERSION,
        },
    )

    manager = ContradictionManager()
    manager_state = manager.query([detected])

    reducer = ContradictionReducer()
    reducer.apply(detected)
    reducer_state = reducer.snapshot()

    assert manager_state.contradictions == reducer_state.contradictions
    assert manager_state.severity_summary == reducer_state.severity_summary
    assert manager_state.analysis_id == reducer_state.analysis_id
    assert manager_state.template_version == reducer_state.template_version
    assert manager_state.template_version == CONTRADICTION_TEMPLATE_VERSION


def test_contradiction_intent_events_after_checkpoint_no_recompute():
    """Zorunlu 1 critical lock: intent events AFTER a CONTRADICTION_DETECTED
    checkpoint do NOT cause the manager or reducer to re-derive contradictions.

    Even though the intent events (with shared files / different agents)
    would, if fed to the live detector, produce a contradiction, neither
    manager nor reducer runs the detector. Both return the checkpoint.
    """
    detected = MockEvent(
        EventType.CONTRADICTION_DETECTED.value,
        id="10",
        payload={
            "context_key": "default",
            "contradictions": [],
            "severity_summary": {},
            "evidence_event_ids": ["1"],
            "template_version": CONTRADICTION_TEMPLATE_VERSION,
        },
    )
    events = [
        MockEvent(EventType.TASK_STARTED.value, id="1", payload={"task": "A"}),
        detected,
        MockEvent(EventType.TASK_STARTED.value, id="2", payload={"task": "B"}),
        MockEvent(EventType.TASK_STARTED.value, id="3", payload={"task": "C"}),
    ]

    manager = ContradictionManager()
    manager_state = manager.query(events)

    reducer = ContradictionReducer()
    for e in events:
        reducer.apply(e)
    reducer_state = reducer.snapshot()

    assert manager_state.contradictions == []
    assert reducer_state.contradictions == []
    assert manager_state.analysis_id == reducer_state.analysis_id


def test_contradiction_order_independence():
    """canonical_event_sort: manager must produce the same analysis_id
    regardless of the order of events in the input list."""
    detected = MockEvent(
        EventType.CONTRADICTION_DETECTED.value,
        id="10",
        payload={
            "context_key": "default",
            "contradictions": [
                {
                    "severity": "warning",
                    "severity_score": 50,
                    "agents": ["a", "b"],
                    "related_files": [],
                    "a_goal": "x",
                    "b_goal": "y",
                    "evidence_intent_ids": [],
                }
            ],
            "severity_summary": {"warning": 1},
            "evidence_event_ids": ["1", "2"],
            "template_version": 1,
        },
    )
    e1 = MockEvent(EventType.TASK_STARTED.value, id="1")
    e2 = MockEvent(EventType.TASK_STARTED.value, id="2")

    state1 = ContradictionManager().query([detected, e1, e2])
    state2 = ContradictionManager().query([e2, e1, detected])
    state3 = ContradictionManager().query([e1, detected, e2])

    assert state1.analysis_id == state2.analysis_id == state3.analysis_id
    assert state1.contradictions == state2.contradictions == state3.contradictions


def test_stable_contradiction_id():
    assert _stable_contradiction_id(["1", "2"]) == _stable_contradiction_id(["2", "1"])
    assert _stable_contradiction_id(["1", "2"]) != _stable_contradiction_id(["1", "3"])
    assert _stable_contradiction_id(["1", "2"]) != _stable_contradiction_id(["1"])
    assert _stable_contradiction_id(["1", "2"]).startswith("contradiction-")


def test_contradiction_key_of_deterministic():
    """Zorunlu 2: _contradiction_key_of must NOT use frozenset.__repr__
    (PYTHONHASHSEED-dependent). Sorted join only â€” replay-safe."""
    k1 = _contradiction_key_of(["intent_a", "intent_b"])
    k2 = _contradiction_key_of(["intent_b", "intent_a"])
    k3 = _contradiction_key_of(["intent_a", "intent_c"])

    assert k1 == k2
    assert k1 != k3
    assert "frozenset" not in k1
    assert "|" in k1


def test_contradiction_unknown_event_tolerance():
    """Reducer.apply() must be a no-op for any event whose type is not
    CONTRADICTION_DETECTED. Unknown / unrelated event types do not pollute
    the snapshot. (Replay engine's _is_known_event is the broader gate;
    this is the reducer-level idempotency contract.)"""
    reducer = ContradictionReducer()
    reducer.apply(MockEvent(EventType.TASK_COMPLETED.value, id="1"))
    reducer.apply(MockEvent(EventType.FAILURE.value, id="2"))
    reducer.apply(MockEvent("totally_unknown_type", id="3"))

    state = reducer.snapshot()
    assert state.contradictions == []
    assert state.severity_summary == {}
    assert state.evidence_event_ids == []


def test_contradiction_reducer_idempotency():
    """Re-applying the same event (same id) is a no-op. Crucial for replay safety."""
    detected = MockEvent(
        EventType.CONTRADICTION_DETECTED.value,
        id="10",
        payload={
            "context_key": "default",
            "contradictions": [
                {
                    "severity": "warning",
                    "severity_score": 50,
                    "agents": [],
                    "related_files": [],
                    "a_goal": "",
                    "b_goal": "",
                    "evidence_intent_ids": [],
                }
            ],
            "severity_summary": {"warning": 1},
            "evidence_event_ids": [],
            "template_version": 1,
        },
    )
    reducer = ContradictionReducer()
    reducer.apply(detected)
    state1 = reducer.snapshot()

    reducer.apply(detected)
    state2 = reducer.snapshot()

    assert state1.analysis_id == state2.analysis_id
    assert state1.contradictions == state2.contradictions
    assert len(state2.contradictions) == 1


def test_contradiction_replay_round_trip_exact_equality():
    """NetleÅŸtirme 2: exact shape equality.

    final_state["contradiction"][context_key] == manager.query(events, context_key).model_dump()

    The replay engine's `all_snapshots()` and the manager's `query()` must
    produce byte-identical dicts for the same event stream.
    """
    detected = MockEvent(
        EventType.CONTRADICTION_DETECTED.value,
        id="10",
        payload={
            "context_key": "default",
            "contradictions": [
                {
                    "severity": "warning",
                    "severity_score": 50,
                    "agents": ["claude", "codex"],
                    "related_files": ["auth.py"],
                    "a_goal": "JWT refactor",
                    "b_goal": "Auth cleanup",
                    "evidence_intent_ids": ["i1", "i2"],
                }
            ],
            "severity_summary": {"warning": 1},
            "evidence_event_ids": ["1", "2"],
            "template_version": CONTRADICTION_TEMPLATE_VERSION,
        },
    )
    events = [
        MockEvent(EventType.TASK_STARTED.value, id="1", payload={"task": "JWT refactor"}),
        detected,
        MockEvent(EventType.TASK_STARTED.value, id="2", payload={"task": "Auth cleanup"}),
    ]

    engine = EventReplayEngine()
    final_state = engine.replay(events)["final_state"]
    manager_state = ContradictionManager().query(events, context_key="default")

    assert final_state["contradiction"]["default"] == manager_state.model_dump()


def test_contradiction_dedup():
    """dedup_contradictions collapses duplicates over the same intent pair,
    keeping the highest severity score."""
    c_warning = {
        "severity": "warning",
        "severity_score": 50,
        "agents": [],
        "related_files": [],
        "a_goal": "",
        "b_goal": "",
        "evidence_intent_ids": ["i1", "i2"],
    }
    c_critical = {
        "severity": "critical",
        "severity_score": 85,
        "agents": [],
        "related_files": [],
        "a_goal": "",
        "b_goal": "",
        "evidence_intent_ids": ["i1", "i2"],
    }
    c_other = {
        "severity": "warning",
        "severity_score": 50,
        "agents": [],
        "related_files": [],
        "a_goal": "",
        "b_goal": "",
        "evidence_intent_ids": ["i3", "i4"],
    }

    result = dedup_contradictions([c_warning, c_critical, c_other])
    assert len(result) == 2
    by_pair = {_contradiction_key_of(c["evidence_intent_ids"]): c for c in result}
    assert by_pair[_contradiction_key_of(["i1", "i2"])]["severity_score"] == 85
    assert by_pair[_contradiction_key_of(["i3", "i4"])]["severity_score"] == 50


def test_contradiction_lifecycle_bound_to_event_type():
    """Zorunlu 3: INCOMPATIBLE_LIFECYCLE must be built from EventType enum
    values that are byte-identical to IntentExtractor's sub_goal vocabulary.

    IntentExtractor writes sub_goal from EventType values:
        TASK_STARTED -> "task_started"
        TASK_COMPLETED -> "task_completed"
        TASK_BLOCKED -> "task_blocked"
        FAILURE -> "failure"           <- NOT TASK_FAILED ("task_failed")
        FILE_MODIFIED -> "file_modified"

    The detector's lifecycle check must match this vocabulary exactly.
    """
    lifecycle_values: set[str] = set()
    for pair in INCOMPATIBLE_LIFECYCLE:
        for value in pair:
            lifecycle_values.add(value)

    assert EventType.TASK_COMPLETED.value in lifecycle_values
    assert EventType.TASK_BLOCKED.value in lifecycle_values
    assert EventType.FAILURE.value in lifecycle_values
    assert "task_failed" not in lifecycle_values

    assert SEVERITY_GOAL_DIVERGENCE == 50
    assert SEVERITY_LIFECYCLE_INCOMPATIBLE_SAME_GOAL == 85
    assert SEVERITY_LIFECYCLE_INCOMPATIBLE_SHARED == 70


def test_contradiction_detector_failure_lifecycle_matches_extractor():
    """Zorunlu 3 lock: a contradiction over (task_completed, failure) lifecycle
    must be detected when the intents carry the exact sub_goal strings that
    IntentExtractor produces â€” i.e. "task_completed" and "failure", never
    "task_failed".

    The detector's INCOMPATIBLE_LIFECYCLE set is the same set that
    IntentExtractor populates via sub_goal â€” they MUST agree by construction.
    """
    from allbrain.domains.reasoning.intent.extractor import IntentExtractor

    a = _make_intent("i1", "codex", "JWT refactor", EventType.TASK_COMPLETED.value, ["auth.py"])
    b = _make_intent("i2", "claude", "JWT refactor", EventType.FAILURE.value, ["auth.py"])

    c = ContradictionDetector()
    detected = c.detect([a, b])

    assert len(detected) == 1
    assert detected[0]["severity_score"] == SEVERITY_LIFECYCLE_INCOMPATIBLE_SAME_GOAL


def test_contradiction_quality_gate_no_uuid7_or_now_in_determinism_path():
    """Quality gate: estimator.py, reducer.py, manager.py must not use uuid7()
    or datetime.now() â€” deterministic hash only. The pipeline write-path
    (and the detector itself) is exempt because it runs at runtime, not
    replay."""
    determinism_critical = ["estimator.py", "reducer.py", "manager.py"]
    base = Path("src/allbrain/domains/analysis/contradiction")
    if not base.exists():
        base = Path("src/allbrain/contradiction")
    for filename in determinism_critical:
        content = (base / filename).read_text(encoding="utf-8")
        assert "uuid7" not in content, f"{filename} uses uuid7 â€” must be deterministic hash"
        assert "datetime.now" not in content, f"{filename} uses datetime.now â€” must be deterministic"
