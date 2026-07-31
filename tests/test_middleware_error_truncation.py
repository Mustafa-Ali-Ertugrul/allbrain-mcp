"""Test tool_call_outcome error message formatting in lifecycle_middleware."""

import tempfile
from pathlib import Path

from allbrain.server.context import BrainContext
from allbrain.server.lifecycle_middleware import _record_outcome
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def test_record_outcome_error_formatting() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        proj_path = Path(tmpdir) / "project"
        proj_path.mkdir()

        engine = create_engine_for_path(db_path)
        try:
            init_db(engine)
            repo = BrainRepository(engine)
            session = repo.create_session(proj_path, "tester")
            context = BrainContext(
                repository=repo,
                project_path=str(proj_path.resolve()),
                active_session=session,
                agent_name="tester",
            )

            # Test short error message (must not duplicate!)
            short_msg = "Invalid session ID"
            _record_outcome(
                context,
                session=session,
                call_id="call-1",
                tool_name="test_tool",
                ok=False,
                duration_ms=10,
                error_type="user_input_error",
                error=short_msg,
            )

            events = repo.list_events(project_path=proj_path)
            assert len(events) == 1
            assert events[0].payload["error"] == "Invalid session ID"

            # Test long error message (>2000 chars)
            long_msg = "X" * 2500
            _record_outcome(
                context,
                session=session,
                call_id="call-2",
                tool_name="test_tool",
                ok=False,
                duration_ms=15,
                error_type="internal_error",
                error=long_msg,
            )

            events = repo.list_events(project_path=proj_path)
            assert len(events) == 2
            assert len(events[1].payload["error"]) == 2001
            assert events[1].payload["error"].endswith("…")
        finally:
            engine.dispose()
