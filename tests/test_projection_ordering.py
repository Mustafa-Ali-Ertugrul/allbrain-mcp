import pytest
from datetime import datetime, timezone, timedelta
from allbrain.models.schemas import EventRead
from allbrain.runtime_core.projections import RuntimeCoreStateBuilder
from pathlib import Path

# Behavioral test for projection ordering
def test_runtime_projection_uses_canonical_order():
    builder = RuntimeCoreStateBuilder()
    
    uuid7_older = "018e9c40-0000-7000-8000-000000000001"
    uuid7_newer = "018e9c40-1000-7000-8000-000000000002"
    
    now = datetime.now(timezone.utc)
    older_time = now - timedelta(days=1)
    newer_time = now + timedelta(days=1)
    
    common_fields = {
        "project_id": 1,
        "session_id": 1,
        "source": "test_source",
        "file_path": "/dev/null",
        "task_hint": "test_hint",
        "importance": 1
    }
    
    # e1: older ID, newer created_at
    e1 = EventRead(
        id=uuid7_older,
        type="test_event",
        payload={"run_id": "run-1", "step": "first"},
        created_at=newer_time,
        payload_version=1,
        **common_fields
    )
    
    # e2: newer ID, older created_at
    e2 = EventRead(
        id=uuid7_newer,
        type="test_event",
        payload={"run_id": "run-1", "step": "second"},
        created_at=older_time,
        payload_version=1,
        **common_fields
    )
    
    # Pass them in reverse order to ensure sorting happens
    events = [e2, e1]
    
    state = builder.build(events)
    
    run_state = state["runs"]["run-1"]
    
    # The events should be processed in canonical order (e1 then e2) based on ID,
    # despite e1 having a newer created_at than e2.
    assert run_state["events"] == [uuid7_older, uuid7_newer]


# Quality gate test for projection ordering contract
def test_quality_gate_no_implicit_created_at_sort():
    src_dir = Path("src/allbrain")
    
    violations = []
    
    for py_file in src_dir.rglob("*.py"):
        if "foundations" in py_file.parts:
            continue
            
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "key=lambda" in content and "created_at" in content and "id" in content:
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if "key=lambda" in line and "created_at" in line and "id" in line:
                    violations.append(f"{py_file}:{i+1}: {line.strip()}")
                    
    assert not violations, f"Found implicit created_at sorting violating the canonical order contract:\n" + "\n".join(violations)

