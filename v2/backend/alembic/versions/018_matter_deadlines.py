"""018_matter_deadlines — lightweight matter calendar deadlines."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "018_matter_deadlines"
down_revision = "017_matter_ingest_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "matter_deadlines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("matter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("matters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_matter_deadlines_matter", "matter_deadlines", ["matter_id", "due_date"])


def downgrade() -> None:
    op.drop_index("idx_matter_deadlines_matter", table_name="matter_deadlines")
    op.drop_table("matter_deadlines")
