from __future__ import annotations

from datetime import UTC, datetime, timezone
from uuid import uuid4

import pytest

from allbrain.events import EventType
from allbrain.foundations import (
    PayloadUpcaster,
    canonical_event_keys,
    canonical_event_sort,
    current_payload_version,
    is_known_event,
    normalize_payload,
)
from allbrain.models.schemas import EventRead
from allbrain.replay import EventReplayEngine
from allbrain.server.app import (
    detect_knowledge_gaps_impl,
    estimate_uncertainty_impl,
    generate_scenarios_impl,
)
from tests.test_sprint12_memory_policy_ui import events as context_events
from tests.test_sprint12_memory_policy_ui import make_context


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    created_at: datetime | None = None,
    payload_version: int | None = None,
) -> EventRead:
    return EventRead(
        id=event_id or str(uuid4()),
        project_id=1,
        session_id=1,
        type=event_type,
        source="test",
        file_path=None,
        payload={},
        task_hint=None,
        importance=1,
        created_at=created_at or datetime(2026, 1, 1, 12, 0, 0),
        payload_version=payload_version if payload_version is not None else current_payload_version(),
    )


def test_payload_version_default_is_1() -> None:
    event = _event("world_state_observed")
    assert event.payload_version == 1


def test_upcaster_identity_v1_to_v1() -> None:
    up = PayloadUpcaster()
    payload, version = up.migrate({"x": 1}, from_version=1, to_version=1)
    assert payload == {"x": 1}
    assert version == 1


def test_upcaster_chain_v1_to_v3() -> None:
    up = PayloadUpcaster()
    up.register(1, 2, lambda p: {**p, "v2": True})
    up.register(2, 3, lambda p: {**p, "v3": True})
    payload, version = up.migrate({"x": 1}, from_version=1, to_version=3)
    assert payload == {"x": 1, "v2": True, "v3": True}
    assert version == 3


def test_upcaster_missing_step_raises() -> None:
    up = PayloadUpcaster()
    up.register(1, 2, lambda p: p)
    with pytest.raises(ValueError, match="no upcaster registered"):
        up.migrate({}, from_version=1, to_version=3)


def test_normalize_payload_v1_passthrough() -> None:
    normalized = normalize_payload({"x": 1}, from_version=1)
    assert normalized == {"x": 1}


def test_canonical_ordering_uuid7_only() -> None:
    e1 = _event("a", event_id="01900000-0000-7000-8000-000000000001")
    e2 = _event("b", event_id="01900000-0000-7000-8000-000000000002")
    e3 = _event("c", event_id="01900000-0000-7000-8000-000000000003")
    sorted_events = canonical_event_sort([e3, e1, e2])
    assert [e.id for e in sorted_events] == [e1.id, e2.id, e3.id]


def test_canonical_ordering_stable_under_created_at_collision() -> None:
    same_time = datetime(2026, 1, 1, 12, 0, 0)
    e1 = _event("a", event_id="01900000-0000-7000-8000-000000000001", created_at=same_time)
    e2 = _event("b", event_id="01900000-0000-7000-8000-000000000002", created_at=same_time)
    e3 = _event("c", event_id="01900000-0000-7000-8000-000000000003", created_at=same_time)
    assert canonical_event_keys([e3, e1, e2]) == [e1.id, e2.id, e3.id]


def test_canonical_ordering_with_mixed_event_types() -> None:
    events = [
        _event("meta_reasoning_completed", event_id="01900000-0000-7000-8000-000000000005"),
        _event("world_state_observed", event_id="01900000-0000-7000-8000-000000000001"),
        _event("foresight_generated", event_id="01900000-0000-7000-8000-000000000004"),
        _event("counterfactual_generated", event_id="01900000-0000-7000-8000-000000000002"),
        _event("scenario_generated", event_id="01900000-0000-7000-8000-000000000003"),
    ]
    ids = canonical_event_keys(events)
    assert ids == sorted(ids)


def test_tolerance_unknown_world_event_skipped(tmp_path) -> None:
    context = make_context(tmp_path)
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="world_state_observed",
        source="test",
        payload={},
    )
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="some_unknown_type_in_world_namespace",
        source="test",
        payload={},
    )
    all_events = context_events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]
    assert "foundations" in replay
    assert replay["foundations"]["unknown_event_count"] >= 1


def test_tolerance_unknown_counterfactual_skipped(tmp_path) -> None:
    context = make_context(tmp_path)
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="counterfactual_generated",
        source="test",
        payload={},
    )
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="brand_new_unknown_type",
        source="test",
        payload={},
    )
    replay = EventReplayEngine().replay(context_events(context))["final_state"]
    assert replay["foundations"]["unknown_event_count"] >= 1


def test_tolerance_unknown_scenario_skipped(tmp_path) -> None:
    context = make_context(tmp_path)
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="scenario_generated",
        source="test",
        payload={},
    )
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="strange_new_event_type",
        source="test",
        payload={},
    )
    replay = EventReplayEngine().replay(context_events(context))["final_state"]
    assert replay["foundations"]["unknown_event_count"] >= 1


def test_tolerance_unknown_foresight_skipped(tmp_path) -> None:
    context = make_context(tmp_path)
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="foresight_generated",
        source="test",
        payload={},
    )
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="brand_new_xyz",
        source="test",
        payload={},
    )
    replay = EventReplayEngine().replay(context_events(context))["final_state"]
    assert replay["foundations"]["unknown_event_count"] >= 1


def test_tolerance_unknown_meta_reasoning_skipped(tmp_path) -> None:
    context = make_context(tmp_path)
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="meta_reasoning_started",
        source="test",
        payload={},
    )
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="brand_new_abc",
        source="test",
        payload={},
    )
    replay = EventReplayEngine().replay(context_events(context))["final_state"]
    assert replay["foundations"]["unknown_event_count"] >= 1


def test_tolerance_unknown_uncertainty_skipped(tmp_path) -> None:
    context = make_context(tmp_path)
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="uncertainty_estimated",
        source="test",
        payload={},
    )
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="brand_new_def",
        source="test",
        payload={},
    )
    replay = EventReplayEngine().replay(context_events(context))["final_state"]
    assert replay["foundations"]["unknown_event_count"] >= 1


def test_tolerance_unknown_information_seeking_skipped(tmp_path) -> None:
    context = make_context(tmp_path)
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="information_need_detected",
        source="test",
        payload={},
    )
    context.repository.append_event(
        project_path=context.project_path,
        session_id=1,
        type="brand_new_ghi",
        source="test",
        payload={},
    )
    replay = EventReplayEngine().replay(context_events(context))["final_state"]
    assert replay["foundations"]["unknown_event_count"] >= 1


def test_replay_state_includes_foundations_meta(tmp_path) -> None:
    context = make_context(tmp_path)
    replay = EventReplayEngine().replay(context_events(context))["final_state"]
    assert replay["foundations"]["ordering"] == "uuid7"
    assert replay["foundations"]["payload_version"] == 1
    assert replay["foundations"]["unknown_event_count"] == 0


def test_zero_behavior_change_golden(tmp_path) -> None:
    context = make_context(tmp_path)

    generate_scenarios_impl(context, action="deploy", scenarios_limit=4)
    detect_knowledge_gaps_impl(context, decision_id="some_id")
    estimate_uncertainty_impl(context, decision_id="some_id")

    all_events = context_events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]

    assert "world" in replay
    assert "scenarios" in replay
    assert "uncertainty" in replay
    assert "foundations" in replay


def test_is_known_event_basic_check() -> None:
    assert is_known_event("world_state_observed") is True
    assert is_known_event("task_completed") is True
    assert is_known_event("some_future_unknown_event") is False


def test_list_events_ordered_by_id_not_created_at(tmp_path) -> None:
    from datetime import datetime

    from allbrain.models.entities import Event
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db, open_session

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, "codex")

    e1 = repo.append_event(
        project_path=project_root,
        session_id=session.id or 0,
        type="x",
        source="test",
        payload={"i": 1},
    )
    e2 = repo.append_event(
        project_path=project_root,
        session_id=session.id or 0,
        type="x",
        source="test",
        payload={"i": 2},
    )
    e3 = repo.append_event(
        project_path=project_root,
        session_id=session.id or 0,
        type="x",
        source="test",
        payload={"i": 3},
    )

    earlier = datetime(2020, 1, 1, tzinfo=UTC)
    later = datetime(2030, 1, 1, tzinfo=UTC)
    with open_session(repo.engine) as db:
        for row in (db.get(Event, e1.id), db.get(Event, e2.id), db.get(Event, e3.id)):
            assert row is not None
        db.get(Event, e1.id).created_at = later
        db.get(Event, e2.id).created_at = earlier
        db.get(Event, e3.id).created_at = later
        db.commit()

    events = repo.list_events(project_path=project_root)
    ids = [event.id for event in events]
    assert ids == canonical_event_keys(events)
    assert ids == sorted(ids)
    assert ids == [e1.id, e2.id, e3.id]


def test_payload_version_persisted_and_stamped(tmp_path) -> None:
    from allbrain.foundations.versioning import current_payload_version
    from allbrain.models.entities import Event
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db, open_session

    engine = create_engine_for_path(tmp_path / "allbrain.db")
    init_db(engine)
    repo = BrainRepository(engine)
    project_root = tmp_path / "project"
    project_root.mkdir()
    session = repo.create_session(project_root, "codex")

    event = repo.append_event(
        project_path=project_root,
        session_id=session.id or 0,
        type="x",
        source="test",
        payload={"k": "v"},
    )

    with open_session(repo.engine) as db:
        row = db.get(Event, event.id)
        assert row is not None
        assert row.payload_version == current_payload_version()

    read = repo.get_event(event.id)
    assert read is not None
    assert read.payload_version == current_payload_version()


def test_upcaster_fires_on_read(tmp_path) -> None:
    from allbrain.foundations.versioning import (
        get_default_upcaster,
    )
    from allbrain.models.entities import Event
    from allbrain.storage import (
        BrainRepository,
        create_engine_for_path,
        ensure_event_payload_version_column,
        init_db,
        open_session,
    )

    up = get_default_upcaster()

    def v1_to_v2(payload: dict) -> dict:
        return {**payload, "v2_field": "default_value"}

    up.register(1, 2, v1_to_v2)
    try:
        assert up.current_version() == 2

        engine = create_engine_for_path(tmp_path / "allbrain.db")
        init_db(engine)
        repo = BrainRepository(engine)
        project_root = tmp_path / "project"
        project_root.mkdir()
        session = repo.create_session(project_root, "codex")

        with open_session(repo.engine) as db:
            row = Event(
                id="01900000-0000-7000-8000-000000000001",
                project_id=1,
                session_id=session.id or 0,
                type="legacy_v1_event",
                source="legacy",
                file_path=None,
                payload_json='{"legacy": true}',
                payload_version=1,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
            )
            project = repo.get_or_create_project(db, project_root)
            row.project_id = project.id or 0
            db.add(row)
            db.commit()

        ensure_event_payload_version_column(engine)
        read = repo.get_event("01900000-0000-7000-8000-000000000001")
        assert read is not None
        assert read.payload["v2_field"] == "default_value"
        assert read.payload["legacy"] is True
        assert read.payload_version == up.current_version()
        assert read.payload_version == 2
    finally:
        up.unregister(1, 2)
        assert up.current_version() == 1
