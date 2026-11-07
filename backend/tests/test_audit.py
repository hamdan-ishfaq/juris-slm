"""Audit API integration tests — Phase 1."""
from __future__ import annotations

import uuid

import pytest

from api_helpers import api_request, register_user


@pytest.mark.integration
def test_audit_list_and_export(api_up):
    owner = register_user(org_name=f"AuditOrg-{uuid.uuid4().hex[:6]}")
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "Audit Matter", "description": "test"},
    )
    assert r.status_code == 200

    r = api_request("GET", "/api/v1/audit?page=1&page_size=5", token=owner["token"])
    assert r.status_code == 200
    body = r.json()
    assert "items" in body and body["total"] >= 1

    r = api_request("GET", "/api/v1/audit/export", token=owner["token"])
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


@pytest.mark.integration
def test_member_cannot_read_audit(api_up):
    member = register_user()
    r = api_request("GET", "/api/v1/audit", token=member["token"])
    assert r.status_code == 403
