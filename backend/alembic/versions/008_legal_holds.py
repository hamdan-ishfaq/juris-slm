"""008_legal_holds — Phase 9B legal hold for eDiscovery retention."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008_legal_holds"
down_revision = "007_org_isolation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matters.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matter_documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("placed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "placed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.create_index("idx_legal_holds_org_id", "legal_holds", ["org_id"])
    op.create_index("idx_legal_holds_matter_id", "legal_holds", ["matter_id"])
    op.create_index("idx_legal_holds_document_id", "legal_holds", ["document_id"])
    op.create_index("idx_legal_holds_status", "legal_holds", ["status"])


def downgrade() -> None:
    op.drop_index("idx_legal_holds_status", table_name="legal_holds")
    op.drop_index("idx_legal_holds_document_id", table_name="legal_holds")
    op.drop_index("idx_legal_holds_matter_id", table_name="legal_holds")
    op.drop_index("idx_legal_holds_org_id", table_name="legal_holds")
    op.drop_table("legal_holds")
