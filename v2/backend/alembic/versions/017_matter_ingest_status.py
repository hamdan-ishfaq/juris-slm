"""017_matter_ingest_status — document ingest status + OCR flag."""
from alembic import op
import sqlalchemy as sa

revision = "017_matter_ingest_status"
down_revision = "016_clause_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matter_documents",
        sa.Column("ingest_status", sa.String(32), nullable=False, server_default="pending"),
    )
    op.add_column("matter_documents", sa.Column("ingest_error", sa.Text(), nullable=True))
    op.add_column(
        "matter_documents",
        sa.Column("ocr_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("matter_documents", "ocr_used")
    op.drop_column("matter_documents", "ingest_error")
    op.drop_column("matter_documents", "ingest_status")
