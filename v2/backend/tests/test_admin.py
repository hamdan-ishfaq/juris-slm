"""Admin API integration tests — Phase 1."""
from __future__ import annotations

import uuid

import pytest

from api_helpers import api_request, register_user, assign_user_to_org_sync as assign_user_to_org


@pytest.mark.integration
def test_member_cannot_list_admin_users(api_up):
    member = register_user()
    r = api_request("GET", "/api/v1/admin/users", token=member["token"])
    assert r.status_code == 403


@pytest.mark.integration
def test_owner_lists_and_updates_role(api_up):
    owner = register_user(org_name=f"AdminOrg-{uuid.uuid4().hex[:6]}")
    member = register_user()

    assert owner["org_id"]
    assign_user_to_org(member["user_id"], owner["org_id"])

    r = api_request("GET", "/api/v1/admin/users", token=owner["token"])
    assert r.status_code == 200
    users = r.json()
    assert any(u["email"] == member["email"] for u in users)

    r = api_request(
        "PUT",
        f"/api/v1/admin/users/{member['user_id']}/role",
        token=owner["token"],
        json_body={"role": "matter_lead"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "matter_lead"


@pytest.mark.integration
def test_owner_cannot_assign_owner_role(api_up):
    owner = register_user(org_name=f"PromoteOrg-{uuid.uuid4().hex[:6]}")
    member = register_user()
    assign_user_to_org(member["user_id"], owner["org_id"])

    r = api_request(
        "PUT",
        f"/api/v1/admin/users/{member['user_id']}/role",
        token=owner["token"],
        json_body={"role": "owner"},
    )
    assert r.status_code == 400


@pytest.mark.integration
def test_owner_cannot_change_own_role(api_up):
    owner = register_user(org_name=f"SelfOrg-{uuid.uuid4().hex[:6]}")
    r = api_request(
        "PUT",
        f"/api/v1/admin/users/{owner['user_id']}/role",
        token=owner["token"],
        json_body={"role": "member"},
    )
    assert r.status_code == 400


@pytest.mark.integration
def test_admin_get_and_patch_org(api_up):
    owner = register_user(org_name=f"OrgSettings-{uuid.uuid4().hex[:6]}")
    r = api_request("GET", "/api/v1/admin/org", token=owner["token"])
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == owner["org_id"]
    assert body["name"].startswith("OrgSettings-")

    r = api_request(
        "PATCH",
        "/api/v1/admin/org",
        token=owner["token"],
        json_body={"name": "Renamed Firm LLP", "settings": {"retention_days": 365}},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed Firm LLP"
    assert r.json()["settings"].get("retention_days") == 365
