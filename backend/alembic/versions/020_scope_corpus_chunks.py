"""Mark chunks of org-uploaded corpora with their org, so they stop being shared with every tenant.

Revision ID: 020_scope_corpus_chunks
Revises: 019_remove_enterprise
"""
from alembic import op

revision = "020_scope_corpus_chunks"
down_revision = "019_remove_enterprise"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE document_chunks AS chunk
        SET metadata = chunk.metadata || jsonb_build_object('org_id', source.org_id::text)
        FROM corpus_sources AS source
        WHERE chunk.document_id = source.document_id
          AND source.org_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE document_chunks AS chunk
        SET metadata = chunk.metadata - 'org_id'
        FROM corpus_sources AS source
        WHERE chunk.document_id = source.document_id
        """
    )
