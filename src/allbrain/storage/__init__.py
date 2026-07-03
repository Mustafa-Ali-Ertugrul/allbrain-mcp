from allbrain.storage.database import (
    create_engine_for_path,
    create_engine_for_url,
    ensure_event_payload_version_column,
    ensure_session_lifecycle_columns,
    ensure_stream_position_columns,
    init_db,
    open_session,
)
from allbrain.storage.repository import BrainRepository

__all__ = [
    "BrainRepository",
    "SnapshotRepo",
    "create_engine_for_path",
    "create_engine_for_url",
    "ensure_event_payload_version_column",
    "ensure_session_lifecycle_columns",
    "ensure_stream_position_columns",
    "init_db",
    "open_session",
]


def __getattr__(name: str):
    if name == "SnapshotRepo":
        from allbrain.storage.snapshot_repo import SnapshotRepo

        return SnapshotRepo
    raise AttributeError(name)
