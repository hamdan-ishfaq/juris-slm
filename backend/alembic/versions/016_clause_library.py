"""016_clause_library — Phase 10E firm clause bank."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "016_clause_library"
down_revision = "015_corpus_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clause_library_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clause_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.String(64), nullable=False, server_default="general"),
        sa.Column("is_standard", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_clause_library_org_type", "clause_library_items", ["org_id", "clause_type"])


def downgrade() -> None:
    op.drop_index("idx_clause_library_org_type", table_name="clause_library_items")
    op.drop_table("clause_library_items")
