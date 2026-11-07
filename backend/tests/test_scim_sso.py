"""Phase 9C — SCIM 2.0 integration tests."""
from __future__ import annotations

import os
import uuid

import httpx
import pytest

from api_helpers import API_BASE, DEFAULT_PASSWORD, register_user


def _enable_scim(monkeypatch):
    monkeypatch.setenv("SCIM_ENABLED", "true")
    from config import settings

    settings.scim_enabled = True


@pytest.mark.integration
def test_scim_create_user_and_deprovision(api_up, monkeypatch):
    _enable_scim(monkeypatch)
    owner = register_user(org_name=f"ScimOrg-{uuid.uuid4().hex[:6]}")

    r = httpx.post(
        f"{API_BASE}/api/v1/admin/scim-token",
        headers={"Authorization": f"Bearer {owner['token']}"},
        timeout=30.0,
    )
    if r.status_code == 404:
        pytest.skip("SCIM not enabled on running API — set SCIM_ENABLED=true")
    assert r.status_code == 200, r.text
    scim_token = r.json()["token"]
    headers = {"Authorization": f"Bearer {scim_token}", "Content-Type": "application/scim+json"}

    email = f"scim_{uuid.uuid4().hex[:8]}@example.com"
    r = httpx.post(
        f"{API_BASE}/scim/v2/Users",
        headers=headers,
        json={"userName": email, "password": DEFAULT_PASSWORD, "externalId": "ext-123"},
        timeout=30.0,
    )
    assert r.status_code == 201, r.text
    user_id = r.json()["id"]

    r = httpx.post(
        f"{API_BASE}/api/v1/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
        timeout=30.0,
    )
    assert r.status_code == 200
    login_token = r.json()["access_token"]

    r = httpx.delete(f"{API_BASE}/scim/v2/Users/{user_id}", headers=headers, timeout=30.0)
    assert r.status_code == 204

    r = httpx.get(f"{API_BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {login_token}"}, timeout=15.0)
    assert r.status_code == 401


@pytest.mark.integration
def test_sso_status_public(api_up):
    r = httpx.get(f"{API_BASE}/api/v1/auth/sso/status", timeout=10.0)
    assert r.status_code == 200
    body = r.json()
    assert "oidc_enabled" in body
    assert "saml_enabled" in body
