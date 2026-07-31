"""Add integrity_hash and meta_json columns to event table.

Revision ID: 0004_integrity_meta_columns

Promotes payload["_meta"]["integrity_hash"] and payload["_meta"] into
dedicated columns for fast SQL access without parsing payload_json.
Backfill: iterate events oldest→newest, extract hash and meta from
payload_json, populate the new columns.
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0004_integrity_meta_columns"
down_revision = "0003_composite_indices"
branch_labels = None
depends_on = None


def _backfill(connection) -> None:
    rows = connection.execute(
        sa.text(
            "SELECT id, payload_json, stream_position FROM event "
            "ORDER BY stream_position ASC"
        )
    ).fetchall()
    for event_id, payload_json, _position in rows:
        integrity_hash: str | None = None
        meta_json: str | None = None
        try:
            payload = json.loads(payload_json)
        except (TypeError, ValueError):
            pass
        else:
            if isinstance(payload, dict):
                meta = payload.get("_meta")
                if isinstance(meta, dict):
                    integrity_hash = meta.get("integrity_hash")
                    meta_json = json.dumps(meta, ensure_ascii=True, sort_keys=True)
                elif isinstance(meta, str) and meta:
                    meta_json = meta
                # Legacy: top-level integrity_hash (early v1.1)
                if integrity_hash is None:
                    top = payload.get("integrity_hash")
                    if isinstance(top, str) and top:
                        integrity_hash = top
        connection.execute(
            sa.text(
                "UPDATE event SET integrity_hash = :ih, meta_json = :mj WHERE id = :eid"
            ),
            {"ih": integrity_hash, "mj": meta_json, "eid": event_id},
        )


def upgrade() -> None:
    op.add_column("event", sa.Column("integrity_hash", sa.String(length=64), nullable=True))
    op.add_column("event", sa.Column("meta_json", sa.Text(), nullable=True))

    connection = op.get_bind()
    _backfill(connection)

    op.create_index("ix_event_integrity_hash", "event", ["integrity_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_event_integrity_hash", table_name="event", if_exists=True)
    op.drop_column("event", "meta_json")
    op.drop_column("event", "integrity_hash")
