"""012_audit_worm — Phase 9E immutable audit hash chain + seals."""
from __future__ import annotations

import hashlib
import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

revision = "012_audit_worm"
down_revision = "011_sso_scim"
branch_labels = None
depends_on = None

GENESIS = hashlib.sha256(b"GENESIS").hexdigest()


def _row_hash(prev: str, row: dict) -> str:
    payload = {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "org_id": str(row["org_id"]) if row["org_id"] else None,
        "action": row["action"],
        "resource_type": row["resource_type"],
        "resource_id": row["resource_id"],
        "timestamp": row["timestamp"].isoformat() if hasattr(row["timestamp"], "isoformat") else str(row["timestamp"]),
        "details": row["details"] or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{prev}|{canonical}".encode()).hexdigest()


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("prev_hash", sa.String(64), nullable=True))
    op.add_column("audit_events", sa.Column("row_hash", sa.String(64), nullable=True))

    op.create_table(
        "audit_seals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seal_date", sa.Date(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chain_tail_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_audit_seals_org_date", "audit_seals", ["org_id", "seal_date"], unique=True)

    conn = op.get_bind()
    rows = conn.execute(
        text(
            """
            SELECT id, user_id, org_id, action, resource_type, resource_id, timestamp, details
            FROM audit_events
            ORDER BY org_id NULLS FIRST, timestamp ASC, id ASC
            """
        )
    ).mappings().all()

    chains: dict[str | None, str] = {}
    for row in rows:
        org_key = str(row["org_id"]) if row["org_id"] else None
        prev = chains.get(org_key, GENESIS)
        rh = _row_hash(prev, dict(row))
        conn.execute(
            text("UPDATE audit_events SET prev_hash = :prev, row_hash = :rh WHERE id = :id"),
            {"prev": prev, "rh": rh, "id": row["id"]},
        )
        chains[org_key] = rh


def downgrade() -> None:
    op.drop_index("idx_audit_seals_org_date", table_name="audit_seals")
    op.drop_table("audit_seals")
    op.drop_column("audit_events", "row_hash")
    op.drop_column("audit_events", "prev_hash")
