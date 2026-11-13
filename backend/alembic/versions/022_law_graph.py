"""Provisions of the shared statutes and the references between them, read by rule. See docs/DECISIONS.md, D-016.

Revision ID: 022_law_graph
Revises: 021_document_descriptions
"""
from alembic import op

revision = "022_law_graph"
down_revision = "021_document_descriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE law_provisions (
            law text NOT NULL,
            article text NOT NULL,
            title text NOT NULL DEFAULT '',
            PRIMARY KEY (law, article)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE law_references (
            from_law text NOT NULL,
            from_article text NOT NULL,
            to_law text NOT NULL,
            to_article text NOT NULL,
            chunk_id bigint NOT NULL,
            PRIMARY KEY (from_law, from_article, to_law, to_article),
            FOREIGN KEY (from_law, from_article) REFERENCES law_provisions (law, article) ON DELETE CASCADE,
            FOREIGN KEY (to_law, to_article) REFERENCES law_provisions (law, article) ON DELETE CASCADE
        )
        """
    )
    op.execute("CREATE INDEX idx_law_references_to ON law_references (to_law, to_article)")


def downgrade() -> None:
    op.execute("DROP TABLE law_references")
    op.execute("DROP TABLE law_provisions")
