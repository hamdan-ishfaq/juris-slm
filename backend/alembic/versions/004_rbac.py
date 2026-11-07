"""004_rbac

Revision ID: 004_rbac
Revises: 67cd5d0da8ec
Create Date: 2026-06-16

"""
from alembic import op
import sqlalchemy as sa


revision = "004_rbac"
down_revision = "67cd5d0da8ec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("settings", sa.dialects.postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("idx_organizations_slug", "organizations", ["slug"], unique=False)

    op.add_column("users", sa.Column("role", sa.String(length=20), server_default="member", nullable=False))
    op.add_column("users", sa.Column("org_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_users_org_id", "users", "organizations", ["org_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint(
        "chk_users_role",
        "users",
        "role IN ('member', 'matter_lead', 'org_admin', 'owner')",
    )
    op.create_index("idx_users_org_id", "users", ["org_id"], unique=False)
    op.create_index("idx_users_role", "users", ["role"], unique=False)

    op.add_column("matters", sa.Column("org_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_matters_org_id", "matters", "organizations", ["org_id"], ["id"], ondelete="CASCADE")

    op.create_table(
        "matter_members",
        sa.Column("matter_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="viewer", nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("invited_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("matter_id", "user_id"),
        sa.CheckConstraint("role IN ('viewer', 'editor', 'owner')", name="chk_matter_members_role"),
    )
    op.create_index("idx_matter_members_user_id", "matter_members", ["user_id"], unique=False)

    op.add_column(
        "matter_documents",
        sa.Column("confidentiality", sa.String(length=20), server_default="internal", nullable=False),
    )
    op.create_check_constraint(
        "chk_matter_documents_confidentiality",
        "matter_documents",
        "confidentiality IN ('internal', 'restricted', 'privileged')",
    )
    op.create_index(
        "idx_matter_documents_confidentiality",
        "matter_documents",
        ["confidentiality"],
        unique=False,
    )

    op.add_column("audit_events", sa.Column("org_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_audit_events_org_id", "audit_events", "organizations", ["org_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index(
        "idx_audit_events_org_id_timestamp",
        "audit_events",
        ["org_id", "timestamp"],
        unique=False,
    )

    # Backfill default org and existing data
    op.execute(
        """
        INSERT INTO organizations (id, name, slug)
        SELECT gen_random_uuid(), 'Default Organization', 'default-org'
        WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE slug = 'default-org')
        """
    )
    op.execute(
        """
        UPDATE matters m
        SET org_id = (SELECT id FROM organizations WHERE slug = 'default-org' LIMIT 1)
        WHERE m.org_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE users u
        SET org_id = (
            SELECT m.org_id FROM matters m WHERE m.user_id = u.id LIMIT 1
        ),
        role = CASE
            WHEN EXISTS (SELECT 1 FROM matters m WHERE m.user_id = u.id) THEN 'owner'
            ELSE u.role
        END
        WHERE u.org_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE users u
        SET org_id = (SELECT id FROM organizations WHERE slug = 'default-org' LIMIT 1)
        WHERE u.org_id IS NULL
        """
    )
    op.execute(
        """
        INSERT INTO matter_members (matter_id, user_id, role)
        SELECT m.id, m.user_id, 'owner'
        FROM matters m
        ON CONFLICT (matter_id, user_id) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE document_chunks dc
        SET metadata = dc.metadata || jsonb_build_object(
            'confidentiality', md.confidentiality,
            'matter_id', md.matter_id::text
        )
        FROM matter_documents md
        WHERE dc.document_id = md.id
          AND NOT (dc.metadata ? 'confidentiality')
        """
    )
    op.execute(
        """
        UPDATE audit_events ae
        SET org_id = u.org_id
        FROM users u
        WHERE ae.user_id = u.id AND ae.org_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_audit_events_org_id_timestamp", table_name="audit_events")
    op.drop_constraint("fk_audit_events_org_id", "audit_events", type_="foreignkey")
    op.drop_column("audit_events", "org_id")

    op.drop_index("idx_matter_documents_confidentiality", table_name="matter_documents")
    op.drop_constraint("chk_matter_documents_confidentiality", "matter_documents", type_="check")
    op.drop_column("matter_documents", "confidentiality")

    op.drop_index("idx_matter_members_user_id", table_name="matter_members")
    op.drop_table("matter_members")

    op.drop_constraint("fk_matters_org_id", "matters", type_="foreignkey")
    op.drop_column("matters", "org_id")

    op.drop_index("idx_users_role", table_name="users")
    op.drop_index("idx_users_org_id", table_name="users")
    op.drop_constraint("chk_users_role", "users", type_="check")
    op.drop_constraint("fk_users_org_id", "users", type_="foreignkey")
    op.drop_column("users", "org_id")
    op.drop_column("users", "role")

    op.drop_index("idx_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
