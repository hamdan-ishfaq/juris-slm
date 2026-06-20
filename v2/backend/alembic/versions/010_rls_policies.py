"""010_rls_policies — Phase 9A Postgres RLS org isolation."""
from alembic import op

revision = "010_rls_policies"
down_revision = "009_org_hardening"
branch_labels = None
depends_on = None

_TABLES = ("matters", "matter_documents", "audit_events", "chat_threads", "legal_holds")


def _policy_sql(table: str) -> str:
    return f"""
        CREATE POLICY {table}_org_isolation ON {table}
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


def upgrade() -> None:
    op.execute("SELECT set_config('app.bypass_rls', 'on', true)")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(_policy_sql(table))


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
