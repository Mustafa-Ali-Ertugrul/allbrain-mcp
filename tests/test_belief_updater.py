import pytest
from allbrain.belief.updater import beta_mean, beta_variance, beta_info_gain, update_state
from allbrain.belief.estimator import tally_outcomes, _outcome_of, _context_key_of, list_known_context_keys, _stable_analysis_id
from allbrain.belief.models import OutcomeKind, BeliefState
from allbrain.events.schemas import EventType

class MockEvent:
    def __init__(self, type, id="", payload=None, task_hint=None):
        self.type = type
        self.id = id
        self.payload = payload or {}
        self.task_hint = task_hint

def test_beta_functions():
    assert beta_mean(1.0, 1.0) == 0.5
    assert beta_mean(2.0, 1.0) == pytest.approx(0.6666, abs=1e-3)
    
    assert beta_variance(1.0, 1.0) == pytest.approx(0.0833, abs=1e-3)
    
    assert beta_info_gain(1.0, 1.0) > 0.0

def test_outcome_of():
    assert _outcome_of(MockEvent(EventType.TASK_COMPLETED.value)) == OutcomeKind.SUCCESS
    assert _outcome_of(MockEvent(EventType.PIPELINE_RUN_COMPLETED.value)) == OutcomeKind.SUCCESS
    assert _outcome_of(MockEvent(EventType.TASK_FAILED.value)) == OutcomeKind.FAILURE
    assert _outcome_of(MockEvent(EventType.TASK_BLOCKED.value)) == OutcomeKind.BLOCKED
    assert _outcome_of(MockEvent("unknown")) is None

def test_context_key_of():
    assert _context_key_of(MockEvent("type", payload={"objective": {"kind": "test_kind"}})) == "test_kind"
    assert _context_key_of(MockEvent("type", task_hint="test_hint")) == "test_hint"
    assert _context_key_of(MockEvent("type")) == "default"

def test_tally_outcomes():
    events = [
        MockEvent(EventType.TASK_COMPLETED.value, id="1", task_hint="test"),
        MockEvent(EventType.TASK_FAILED.value, id="2", task_hint="test"),
        MockEvent(EventType.TASK_BLOCKED.value, id="3", task_hint="test"),
        MockEvent(EventType.TASK_COMPLETED.value, id="4", task_hint="other"),
    ]
    seen_ids = set()
    successes, failures, blocked = tally_outcomes(events, context_key="test", seen_ids=seen_ids)
    
    assert successes == 1
    assert failures == 1
    assert blocked == 1
    assert len(seen_ids) == 4

def test_stable_analysis_id():
    id1 = _stable_analysis_id("test", ["1", "2"])
    id2 = _stable_analysis_id("test", ["2", "1"])
    id3 = _stable_analysis_id("other", ["1", "2"])
    id4 = _stable_analysis_id("test", ["1"])
    
    assert id1 == id2  # Order of evidence doesn't matter
    assert id1 != id3  # Different context matters
    assert id1 != id4  # Different evidence matters
    assert id1.startswith("belief-")

