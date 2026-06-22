import pytest
from allbrain.belief.manager import BeliefManager
from allbrain.belief.reducer import BeliefReducer
from allbrain.events.schemas import EventType
import time
from datetime import datetime

class MockEvent:
    def __init__(self, type, id="", payload=None, task_hint=None, created_at=None):
        self.type = type
        self.id = id
        self.payload = payload or {}
        self.task_hint = task_hint
        self.created_at = created_at or datetime.now()

def test_belief_convergence():
    events = [
        MockEvent(EventType.TASK_COMPLETED.value, id="1", task_hint="test"),
        MockEvent(EventType.TASK_FAILED.value, id="2", task_hint="test"),
        MockEvent(EventType.TASK_COMPLETED.value, id="3", task_hint="other"),
        MockEvent(EventType.TASK_BLOCKED.value, id="4", task_hint="test"),
    ]
    
    manager = BeliefManager()
    manager_state = manager.query(events, context_key="test")
    
    reducer = BeliefReducer()
    for e in events:
        reducer.apply(e)
    reducer_state = reducer.snapshot(context_key="test")
    
    assert manager_state.alpha == reducer_state.alpha
    assert manager_state.beta == reducer_state.beta
    assert manager_state.successes == reducer_state.successes
    assert manager_state.failures == reducer_state.failures
    assert manager_state.blocked == reducer_state.blocked
    assert manager_state.analysis_id == reducer_state.analysis_id

def test_belief_order_independence():
    e1 = MockEvent(EventType.TASK_COMPLETED.value, id="1", task_hint="test", created_at=datetime(2020, 1, 1))
    e2 = MockEvent(EventType.TASK_FAILED.value, id="2", task_hint="test", created_at=datetime(2020, 1, 2))
    
    manager = BeliefManager()
    
    # Order 1
    state1 = manager.query([e1, e2], context_key="test")
    
    # Order 2
    state2 = manager.query([e2, e1], context_key="test")
    
    assert state1.alpha == state2.alpha
    assert state1.beta == state2.beta
    assert state1.analysis_id == state2.analysis_id

def test_belief_reducer_consumes_computed():
    e1 = MockEvent(EventType.TASK_COMPLETED.value, id="1", task_hint="test")
    computed = MockEvent(
        EventType.BELIEF_COMPUTED.value, 
        id="2", 
        payload={"context_key": "test", "successes": 5, "failures": 2, "blocked": 1}
    )
    e3 = MockEvent(EventType.TASK_COMPLETED.value, id="3", task_hint="test")
    
    reducer = BeliefReducer()
    
    # Starts empty
    reducer.apply(e1)
    state1 = reducer.snapshot(context_key="test")
    assert state1.successes == 1
    
    # Authoritative overwrite
    reducer.apply(computed)
    state2 = reducer.snapshot(context_key="test")
    assert state2.successes == 5
    assert state2.failures == 2
    
    # Increments on top of authoritative
    reducer.apply(e3)
    state3 = reducer.snapshot(context_key="test")
    assert state3.successes == 6
    assert state3.failures == 2

def test_manager_consumes_computed():
    e1 = MockEvent(EventType.TASK_COMPLETED.value, id="1", task_hint="test", created_at=datetime(2020, 1, 1))
    computed = MockEvent(
        EventType.BELIEF_COMPUTED.value, 
        id="2", 
        payload={"context_key": "test", "successes": 5, "failures": 2, "blocked": 1},
        created_at=datetime(2020, 1, 2)
    )
    e3 = MockEvent(EventType.TASK_COMPLETED.value, id="3", task_hint="test", created_at=datetime(2020, 1, 3))
    
    manager = BeliefManager()
    
    # Should use authoritative computed event (successes: 5) and completely ignore everything else 
    # (manager query assumes computed event already includes e1 and ignores e3 because it doesn't tally if computed is present)
    # Actually wait - our implementation uses the LAST computed event, and ignores tally if found
    state = manager.query([e1, computed, e3], context_key="test")
    
    # According to our manager implementation, it uses the computed event and returns immediately
    assert state.successes == 5
    assert state.failures == 2
