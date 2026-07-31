"""Test save_event public registered tool accepts and records explicit agent_id."""

import tempfile
from pathlib import Path

from allbrain.server.context import BrainContext
from allbrain.server.tools.events import save_event_impl
from allbrain.storage import BrainRepository, create_engine_for_path, init_db


def test_save_event_impl_accepts_agent_id() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        proj_path = Path(tmpdir) / "project"
        proj_path.mkdir()

        engine = create_engine_for_path(db_path)
        try:
            init_db(engine)
            repo = BrainRepository(engine)
            session = repo.create_session(proj_path, "default_agent")
            context = BrainContext(
                repository=repo,
                project_path=str(proj_path.resolve()),
                active_session=session,
                agent_name="default_agent",
            )

            res = save_event_impl(
                context,
                type="task_created",
                payload={"goal": "test agent_id"},
                agent_id="custom_agent_x",
            )
            assert res is not None
            assert res.ok is True, f"Error: {res.error}"

            events = repo.list_events(project_path=proj_path)
            saved = [e for e in events if e.type == "task_created"]
            assert len(saved) == 1, f"expected exactly one task_created event, got {events!r}"
            assert saved[0].agent_id == "custom_agent_x"
        finally:
            engine.dispose()
