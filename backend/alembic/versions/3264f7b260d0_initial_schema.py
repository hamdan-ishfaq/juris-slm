"""initial schema

Revision ID: 3264f7b260d0
Revises: 
Create Date: 2026-03-19 20:03:04.262732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3264f7b260d0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums with conditional DO blocks (portable)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
            CREATE TYPE userrole AS ENUM ('user', 'admin', 'owner');
        END IF;
    END$$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'accesslevel') THEN
            CREATE TYPE accesslevel AS ENUM ('level_1', 'level_2', 'level_3');
        END IF;
    END$$;
    """)
    
    # Create users table
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role userrole NOT NULL DEFAULT 'user',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)")
    
    # Create documents table
    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            access_level accesslevel NOT NULL DEFAULT 'level_1',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_owner_id ON documents(owner_id)")
    
    # Create query_traces table
    op.execute("""
        CREATE TABLE IF NOT EXISTS query_traces (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            query TEXT NOT NULL,
            retrieved_chunks INTEGER,
            confidence_score FLOAT,
            response TEXT,
            model_used VARCHAR(100),
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_query_traces_user_id ON query_traces(user_id)")
    
    # Create chat_messages table
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            role VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_chat_messages_user_id ON chat_messages(user_id)")


def downgrade() -> None:
    # Drop tables
    op.execute("DROP TABLE IF EXISTS chat_messages")
    op.execute("DROP TABLE IF EXISTS query_traces")
    op.execute("DROP TABLE IF EXISTS documents")
    op.execute("DROP TABLE IF EXISTS users")
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS accesslevel")
    op.execute("DROP TYPE IF EXISTS userrole")
