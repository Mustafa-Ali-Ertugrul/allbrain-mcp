SNAPSHOT_SCHEMA_VERSION = "7.2"
# 7.3: open tasks drop on task_deleted and on label-only completion. 7.2
# snapshots are deliberately not reducer-compatible: their stored open_tasks
# still carry deleted/completed tasks, so they must be rebuilt by full replay.
REDUCER_VERSION = "7.3"
COMPRESSION_VERSION = "1.1"

COMPATIBLE_SNAPSHOT_SCHEMA_VERSIONS = {"3.1", "4.0", "5.0", "6.0", "7.0", "7.1", SNAPSHOT_SCHEMA_VERSION}


def snapshot_versions() -> dict[str, str]:
    return {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "reducer_version": REDUCER_VERSION,
        "compression_version": COMPRESSION_VERSION,
    }


def is_compatible(metadata: dict) -> bool:
    return (
        metadata.get("snapshot_schema_version") in COMPATIBLE_SNAPSHOT_SCHEMA_VERSIONS
        and metadata.get("reducer_version") in {"3.1", "4.0", "5.0", "6.0", "7.0", "7.1", REDUCER_VERSION}
        and metadata.get("compression_version") == COMPRESSION_VERSION
    )
