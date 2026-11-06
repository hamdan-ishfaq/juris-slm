"""Phase 2.1 — hybrid search: tsvector column + GIN index for BM25/FTS branch.

Revision ID: 005_hybrid_search
Revises: 004_rbac
Create Date: 2026-06-17
"""
from alembic import op

revision = "005_hybrid_search"
down_revision = "004_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN IF NOT EXISTS content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_content_tsv
        ON document_chunks USING GIN (content_tsv)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_content_tsv")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_tsv")
