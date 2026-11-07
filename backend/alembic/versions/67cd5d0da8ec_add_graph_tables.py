"""add_graph_tables

Revision ID: 67cd5d0da8ec
Revises: 003_fix_doc_chunks
Create Date: 2026-05-28 17:22:19.300527

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '67cd5d0da8ec'
down_revision = '003_fix_doc_chunks'
branch_labels = None
depends_on = None



def upgrade() -> None:
    op.create_table('graph_nodes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['matter_documents.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('graph_edges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_node_id', sa.UUID(), nullable=False),
        sa.Column('target_node_id', sa.UUID(), nullable=False),
        sa.Column('relationship', sa.String(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['source_node_id'], ['graph_nodes.id']),
        sa.ForeignKeyConstraint(['target_node_id'], ['graph_nodes.id']),
        sa.PrimaryKeyConstraint('id')
    )




def downgrade() -> None:
    op.drop_table('graph_edges')
    op.drop_table('graph_nodes')

