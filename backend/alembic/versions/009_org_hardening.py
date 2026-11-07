"""009_org_hardening — Phase 9A NOT NULL + chat_messages/graph org_id."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009_org_hardening"
down_revision = "008_legal_holds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE matter_documents md
        SET org_id = m.org_id
        FROM matters m
        WHERE md.matter_id = m.id AND md.org_id IS NULL AND m.org_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE matters
        SET org_id = (SELECT id FROM organizations WHERE slug = 'default-org' LIMIT 1)
        WHERE org_id IS NULL
        """
    )
    op.alter_column("matters", "org_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column("matter_documents", "org_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    op.add_column("chat_messages", sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_chat_messages_org_id",
        "chat_messages",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        """
        UPDATE chat_messages cm
        SET org_id = ct.org_id
        FROM chat_threads ct
        WHERE cm.thread_id = ct.id AND ct.org_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE chat_messages cm
        SET org_id = u.org_id
        FROM chat_threads ct
        JOIN users u ON u.id = ct.user_id
        WHERE cm.thread_id = ct.id AND cm.org_id IS NULL AND u.org_id IS NOT NULL
        """
    )

    op.add_column("graph_nodes", sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_graph_nodes_org_id",
        "graph_nodes",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        """
        UPDATE graph_nodes gn
        SET org_id = md.org_id
        FROM matter_documents md
        WHERE gn.document_id = md.id AND md.org_id IS NOT NULL
        """
    )

    op.create_index(
        "idx_document_chunks_metadata_org_id",
        "document_chunks",
        [sa.text("(metadata->>'org_id')")],
        unique=False,
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("idx_document_chunks_metadata_org_id", table_name="document_chunks")
    op.drop_constraint("fk_graph_nodes_org_id", "graph_nodes", type_="foreignkey")
    op.drop_column("graph_nodes", "org_id")
    op.drop_constraint("fk_chat_messages_org_id", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "org_id")
    op.alter_column("matter_documents", "org_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("matters", "org_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
