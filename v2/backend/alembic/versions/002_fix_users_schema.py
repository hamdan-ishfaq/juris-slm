"""fix_users_schema

Revision ID: 002_fix_users
Revises: f75d11423144
Create Date: 2026-05-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_fix_users'
down_revision = 'f75d11423144'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix users table only
    op.alter_column('users', 'email', existing_type=sa.TEXT(), type_=sa.String(255), existing_nullable=False)
    op.alter_column('users', 'password_hash', existing_type=sa.TEXT(), type_=sa.String(255), existing_nullable=False)
    op.alter_column('users', 'created_at', existing_type=postgresql.TIMESTAMP(timezone=True), type_=sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'), existing_server_default=None)


def downgrade() -> None:
    op.alter_column('users', 'created_at', existing_type=sa.DateTime(timezone=True), type_=postgresql.TIMESTAMP(timezone=True), nullable=True, existing_server_default=sa.text('NOW()'))
    op.alter_column('users', 'password_hash', existing_type=sa.String(255), type_=sa.TEXT(), existing_nullable=False)
    op.alter_column('users', 'email', existing_type=sa.String(255), type_=sa.TEXT(), existing_nullable=False)
