"""011_sso_scim — Phase 9C enterprise SSO + SCIM provisioning."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011_sso_scim"
down_revision = "010_rls_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("external_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("idp_source", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_users_external_id", "users", ["external_id"], unique=False)

    op.create_table(
        "scim_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("label", sa.String(128), nullable=False, server_default="default"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_scim_tokens_org_id", "scim_tokens", ["org_id"])


def downgrade() -> None:
    op.drop_index("idx_scim_tokens_org_id", table_name="scim_tokens")
    op.drop_table("scim_tokens")
    op.drop_index("idx_users_external_id", table_name="users")
    op.drop_column("users", "disabled_at")
    op.drop_column("users", "idp_source")
    op.drop_column("users", "external_id")
