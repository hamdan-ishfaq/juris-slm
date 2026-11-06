"""019_remove_enterprise — drop SSO, SCIM, WORM, legal hold, clause library and deadlines."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019_remove_enterprise"
down_revision = "018_matter_deadlines"
branch_labels = None
depends_on = None


_UUID = postgresql.UUID(as_uuid=True)


def _org_fk() -> sa.ForeignKey:
    return sa.ForeignKey("organizations.id", ondelete="CASCADE")


def _user_fk() -> sa.ForeignKey:
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False)


def upgrade() -> None:
    # Accounts that could only sign in through SSO have no usable password now.
    op.execute(
        "UPDATE users SET disabled_at = NOW() "
        "WHERE password_hash IN ('sso-only', 'oidc-only') AND disabled_at IS NULL"
    )
    op.drop_table("matter_deadlines")
    op.drop_table("clause_library_items")
    op.drop_table("audit_seals")
    op.drop_table("scim_tokens")
    op.execute("DROP POLICY IF EXISTS legal_holds_org_isolation ON legal_holds")
    op.drop_table("legal_holds")
    op.drop_index("idx_users_external_id", table_name="users")
    op.drop_column("users", "idp_source")
    op.drop_column("users", "external_id")


def downgrade() -> None:
    """Restores the schema. Data in the dropped tables is not recoverable."""
    op.add_column("users", sa.Column("external_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("idp_source", sa.String(32), nullable=True))
    op.create_index("idx_users_external_id", "users", ["external_id"], unique=False)

    op.create_table(
        "legal_holds",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("org_id", _UUID, _org_fk(), nullable=False),
        sa.Column("matter_id", _UUID, sa.ForeignKey("matters.id", ondelete="CASCADE"), nullable=True),
        sa.Column("document_id", _UUID, sa.ForeignKey("matter_documents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("placed_by", _UUID, _user_fk(), nullable=True),
        sa.Column("placed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.create_index("idx_legal_holds_org_id", "legal_holds", ["org_id"])
    op.create_index("idx_legal_holds_matter_id", "legal_holds", ["matter_id"])
    op.create_index("idx_legal_holds_document_id", "legal_holds", ["document_id"])
    op.create_index("idx_legal_holds_status", "legal_holds", ["status"])
    op.execute("ALTER TABLE legal_holds ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE legal_holds FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY legal_holds_org_isolation ON legal_holds
        FOR ALL
        USING (
            current_setting('app.bypass_rls', true) = 'on'
            OR (
                current_setting('app.org_id', true) <> ''
                AND org_id = current_setting('app.org_id', true)::uuid
            )
        )
        WITH CHECK (
            current_setting('app.bypass_rls', true) = 'on'
            OR (
                current_setting('app.org_id', true) <> ''
                AND org_id = current_setting('app.org_id', true)::uuid
            )
        )
        """
    )

    op.create_table(
        "scim_tokens",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("org_id", _UUID, _org_fk(), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("label", sa.String(128), nullable=False, server_default="default"),
        sa.Column("created_by", _UUID, _user_fk(), nullable=True),
        _created_at(),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_scim_tokens_org_id", "scim_tokens", ["org_id"])

    op.create_table(
        "audit_seals",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("org_id", _UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seal_date", sa.Date(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_event_id", _UUID, nullable=True),
        sa.Column("last_event_id", _UUID, nullable=True),
        sa.Column("chain_tail_hash", sa.String(64), nullable=False),
        _created_at(),
    )
    op.create_index("idx_audit_seals_org_date", "audit_seals", ["org_id", "seal_date"], unique=True)

    op.create_table(
        "clause_library_items",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("org_id", _UUID, _org_fk(), nullable=False),
        sa.Column("clause_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.String(64), nullable=False, server_default="general"),
        sa.Column("is_standard", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", _UUID, _user_fk(), nullable=True),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("idx_clause_library_org_type", "clause_library_items", ["org_id", "clause_type"])

    op.create_table(
        "matter_deadlines",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("matter_id", _UUID, sa.ForeignKey("matters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", _UUID, _org_fk(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", _UUID, _user_fk(), nullable=True),
        _created_at(),
    )
    op.create_index("idx_matter_deadlines_matter", "matter_deadlines", ["matter_id", "due_date"])
