"""007_org_isolation — Phase 9A multi-tenant org isolation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_org_isolation"
down_revision = "006_chat_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matter_documents", sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_matter_documents_org_id",
        "matter_documents",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.execute(
        """
        UPDATE matters m
        SET org_id = u.org_id
        FROM users u
        WHERE m.user_id = u.id AND m.org_id IS NULL AND u.org_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE matters
        SET org_id = (SELECT id FROM organizations WHERE slug = 'default-org' LIMIT 1)
        WHERE org_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE matter_documents md
        SET org_id = m.org_id
        FROM matters m
        WHERE md.matter_id = m.id
        """
    )
    op.execute(
        """
        UPDATE document_chunks dc
        SET metadata = jsonb_set(
            COALESCE(dc.metadata, '{}'::jsonb),
            '{org_id}',
            to_jsonb(md.org_id::text),
            true
        )
        FROM matter_documents md
        WHERE dc.document_id = md.id
          AND COALESCE(dc.metadata->>'kind', '') != 'law'
          AND md.org_id IS NOT NULL
        """
    )

    op.add_column("chat_threads", sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_chat_threads_org_id",
        "chat_threads",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE chat_threads ct
        SET org_id = m.org_id
        FROM matters m
        WHERE ct.matter_id = m.id AND m.org_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE chat_threads ct
        SET org_id = u.org_id
        FROM users u
        WHERE ct.org_id IS NULL AND ct.user_id = u.id AND u.org_id IS NOT NULL
        """
    )

    op.create_index("idx_matters_org_id", "matters", ["org_id"], unique=False)
    op.create_index("idx_matter_documents_org_id", "matter_documents", ["org_id"], unique=False)
    op.create_index("idx_matter_documents_org_matter", "matter_documents", ["org_id", "matter_id"], unique=False)
    op.create_index("idx_chat_threads_org_id", "chat_threads", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_chat_threads_org_id", table_name="chat_threads")
    op.drop_index("idx_matter_documents_org_matter", table_name="matter_documents")
    op.drop_index("idx_matter_documents_org_id", table_name="matter_documents")
    op.drop_index("idx_matters_org_id", table_name="matters")
    op.drop_constraint("fk_chat_threads_org_id", "chat_threads", type_="foreignkey")
    op.drop_column("chat_threads", "org_id")
    op.drop_constraint("fk_matter_documents_org_id", "matter_documents", type_="foreignkey")
    op.drop_column("matter_documents", "org_id")
