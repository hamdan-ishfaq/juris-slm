"""One embedded description per document, used to find the documents a question names. See docs/DECISIONS.md, D-015.

Keyed by document_id like document_chunks, with no foreign key, so uploaded documents and benchmark documents work the
same way. Rows are deleted with the document's chunks.

Revision ID: 021_document_descriptions
Revises: 020_scope_corpus_chunks
"""
from alembic import op

revision = "021_document_descriptions"
down_revision = "020_scope_corpus_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE document_descriptions (
            document_id uuid PRIMARY KEY,
            embedding vector(1024) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE document_descriptions")
