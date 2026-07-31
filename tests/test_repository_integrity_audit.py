"""Test repository integrity verification and CLI doctor --verify-integrity."""

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from allbrain.cli.main import app
from allbrain.storage import BrainRepository, create_engine_for_path, init_db

runner = CliRunner()


def test_repository_verify_integrity() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        proj_path = Path(tmpdir) / "project"
        proj_path.mkdir()

        engine = create_engine_for_path(db_path)
        try:
            init_db(engine)
            repo = BrainRepository(engine)
            session = repo.create_session(proj_path, "tester")
            session_id = session.id or 0

            repo.append_event(
                project_path=proj_path,
                session_id=session_id,
                type="file_modified",
                source="test",
                payload={"step": 1},
            )
            repo.append_event(
                project_path=proj_path,
                session_id=session_id,
                type="file_modified",
                source="test",
                payload={"step": 2},
            )

            # Untampered check
            res = repo.verify_integrity(proj_path)
            assert res["ok"] is True
            assert res["total_events"] == 2
            assert res["mismatches"] == []

            # Tamper with event 2 payload data while retaining stored hash
            from sqlmodel import select

            from allbrain.storage.database import open_write_session
            from allbrain.storage.repository import Event

            with open_write_session(engine) as db:
                evt2 = db.exec(select(Event).where(Event.stream_position == 2)).first()
                assert evt2 is not None
                data = json.loads(evt2.payload_json)
                data["step"] = 999  # Tamper content
                evt2.payload_json = json.dumps(data)
                db.add(evt2)
                db.commit()

            # Audit must detect mismatch at stream position 2
            res2 = repo.verify_integrity(proj_path)
            assert res2["ok"] is False
            assert res2["total_events"] == 2
            assert 2 in res2["mismatches"]

            # CLI doctor --verify-integrity must report failure
            cli_res = runner.invoke(
                app,
                ["doctor", "--db-path", str(db_path), "--project", str(proj_path), "--verify-integrity"],
            )
            assert cli_res.exit_code == 1
            assert "FAIL  Integrity:" in cli_res.output
        finally:
            engine.dispose()
