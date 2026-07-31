from __future__ import annotations

from pathlib import Path

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DbSession
from sqlmodel import select

from allbrain.config import canonicalize_project_path
from allbrain.models.entities import Project, QueueItemRecord, SnapshotRecord
from allbrain.storage.database import open_session


class ProjectRepository:
    """Project-scoped storage: lookup/create projects and project-wide counts."""

    def __init__(self, engine: Engine, *, owns_engine: bool = False):
        self.engine = engine
        self.owns_engine = owns_engine

    def close(self) -> None:
        if self.owns_engine:
            self.engine.dispose()

    def get_or_create_project(self, db: DbSession, project_path: str | Path | None) -> Project:
        """Get existing project or create new one for the given path.

        Canonicalizes project path for consistent lookups.  Handles the
        project-creation race between concurrent writers by retrying the
        lookup if the insert collides on the unique canonical path.
        """
        canonical_path = canonicalize_project_path(project_path)
        project = db.exec(select(Project).where(Project.canonical_project_path == canonical_path)).first()
        if project is not None:
            return project

        project = Project(
            canonical_project_path=canonical_path,
            name=Path(canonical_path).name or canonical_path,
        )
        db.add(project)
        try:
            # Keep project creation inside the caller's transaction.  A nested
            # savepoint preserves the race-safe lookup without committing an
            # outer event/session write prematurely.
            with db.begin_nested():
                db.flush()
        except IntegrityError:
            # Another writer created the project between our lookup and insert.
            stale = project
            project = db.exec(select(Project).where(Project.canonical_project_path == canonical_path)).first()
            if project is None:
                raise
            # A nested rollback does not necessarily remove the transient
            # object from ``session.new``.  Expunge it so the enclosing commit
            # cannot retry the duplicate INSERT.
            if stale in db:
                db.expunge(stale)
        db.refresh(project)
        return project

    def get_project_by_path(self, project_path: str | Path | None) -> Project | None:
        canonical_path = canonicalize_project_path(project_path)
        with open_session(self.engine) as db:
            return db.exec(select(Project).where(Project.canonical_project_path == canonical_path)).first()

    def count_snapshots(self, *, project_path: str | Path | None) -> int:
        project = self.get_project_by_path(project_path)
        if project is None:
            return 0
        with open_session(self.engine) as db:
            statement = (
                select(func.count(SnapshotRecord.id))
                .select_from(SnapshotRecord)
                .where(SnapshotRecord.project_id == project.id)
            )
            return int(db.exec(statement).one())

    def queue_state_counts(self) -> dict[str, int]:
        with open_session(self.engine) as db:
            rows = db.exec(select(QueueItemRecord.state, func.count()).group_by(QueueItemRecord.state)).all()
        return dict(sorted((str(state), int(count)) for state, count in rows))
