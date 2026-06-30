SNAPSHOT_SCHEMA_VERSION = "7.1"
REDUCER_VERSION = "7.1"
COMPRESSION_VERSION = "1.1"

COMPATIBLE_SNAPSHOT_SCHEMA_VERSIONS = {"3.1", "4.0", "5.0", "6.0", "7.0", SNAPSHOT_SCHEMA_VERSION}


def snapshot_versions() -> dict[str, str]:
    return {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "reducer_version": REDUCER_VERSION,
        "compression_version": COMPRESSION_VERSION,
    }


def is_compatible(metadata: dict) -> bool:
    return (
        metadata.get("snapshot_schema_version") in COMPATIBLE_SNAPSHOT_SCHEMA_VERSIONS
        and metadata.get("reducer_version") in {"3.1", "4.0", "5.0", "6.0", "7.0", REDUCER_VERSION}
        and metadata.get("compression_version") == COMPRESSION_VERSION
    )
