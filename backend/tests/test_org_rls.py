"""Phase 9A — Postgres RLS org isolation integration tests."""
from __future__ import annotations

import uuid

import pytest

from api_helpers import api_request, register_user


@pytest.mark.integration
def test_rls_blocks_cross_org_matter_read(api_up):
    org_a = register_user(org_name=f"RLSA-{uuid.uuid4().hex[:6]}")
    org_b = register_user(org_name=f"RLSB-{uuid.uuid4().hex[:6]}")

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=org_a["token"],
        json_body={"name": "RLS Matter", "description": "rls test"},
    )
    assert r.status_code == 200
    matter_id = r.json()["id"]

    r = api_request("GET", f"/api/v1/matters/{matter_id}", token=org_b["token"])
    assert r.status_code == 404


@pytest.mark.integration
def test_dev_master_in_default_org(api_up):
    """9A.2e — dev master must belong to default-org, not a separate dev org."""
    import os

    from api_helpers import API_BASE, DEFAULT_PASSWORD

    email = os.environ.get("DEV_MASTER_EMAIL", "devmaster@example.com")
    password = os.environ.get("DEV_MASTER_PASSWORD", "DevMasterPass123!")
    import httpx

    r = httpx.post(
        f"{API_BASE}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30.0,
    )
    if r.status_code != 200:
        pytest.skip("Dev master not enabled in this environment")
    me = httpx.get(
        f"{API_BASE}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {r.json()['access_token']}"},
        timeout=15.0,
    )
    assert me.status_code == 200
    org_id = me.json().get("org_id")
    assert org_id

    import psycopg

    db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://juris:juris_password@localhost:5433/juris_db")
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg.connect(sync_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM organizations WHERE id = %s", (org_id,))
            row = cur.fetchone()
    assert row and row[0] == "default-org"
