"""fix_document_chunks_created_at

Revision ID: 003_fix_doc_chunks
Revises: 002_fix_users
Create Date: 2026-05-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_fix_doc_chunks'
down_revision = '002_fix_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('document_chunks', 'created_at', existing_type=postgresql.TIMESTAMP(), type_=sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))


def downgrade() -> None:
    op.alter_column('document_chunks', 'created_at', existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(), nullable=True, server_default=sa.text('NOW()'))
