from allbrain.storage.database import (
    create_engine_for_path,
    ensure_event_payload_version_column,
    init_db,
    open_session,
)
from allbrain.storage.repository import BrainRepository

__all__ = [
    "BrainRepository",
    "SnapshotRepo",
    "create_engine_for_path",
    "ensure_event_payload_version_column",
    "init_db",
    "open_session",
]


def __getattr__(name: str):
    if name == "SnapshotRepo":
        from allbrain.storage.snapshot_repo import SnapshotRepo

        return SnapshotRepo
    raise AttributeError(name)
