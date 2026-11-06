"""Phase 9A — cross-org matter isolation integration tests."""
from __future__ import annotations

import uuid

import pytest

from api_helpers import api_request, register_user


@pytest.mark.integration
def test_cross_org_cannot_get_matter(api_up):
    org_a = register_user(org_name=f"OrgA-{uuid.uuid4().hex[:6]}")
    org_b = register_user(org_name=f"OrgB-{uuid.uuid4().hex[:6]}")

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=org_a["token"],
        json_body={"name": "Org A Matter", "description": "isolated"},
    )
    assert r.status_code == 200
    matter_id = r.json()["id"]

    r = api_request("GET", f"/api/v1/matters/{matter_id}", token=org_b["token"])
    assert r.status_code == 404


@pytest.mark.integration
def test_cross_org_cannot_delete_matter(api_up):
    org_a = register_user(org_name=f"DelA-{uuid.uuid4().hex[:6]}")
    org_b = register_user(org_name=f"DelB-{uuid.uuid4().hex[:6]}")

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=org_a["token"],
        json_body={"name": "Protected Matter", "description": "isolated"},
    )
    matter_id = r.json()["id"]

    r = api_request("DELETE", f"/api/v1/matters/{matter_id}", token=org_b["token"])
    assert r.status_code == 404

    r = api_request("GET", f"/api/v1/matters/{matter_id}", token=org_a["token"])
    assert r.status_code == 200


@pytest.mark.integration
def test_cross_org_matter_not_in_list(api_up):
    org_a = register_user(org_name=f"ListA-{uuid.uuid4().hex[:6]}")
    org_b = register_user(org_name=f"ListB-{uuid.uuid4().hex[:6]}")

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=org_a["token"],
        json_body={"name": "Hidden From B", "description": "isolated"},
    )
    assert r.status_code == 200
    hidden_id = r.json()["id"]

    r = api_request("GET", "/api/v1/matters", token=org_b["token"])
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()}
    assert hidden_id not in ids


@pytest.mark.integration
def test_cross_org_cannot_upload_document(api_up):
    org_a = register_user(org_name=f"UpA-{uuid.uuid4().hex[:6]}")
    org_b = register_user(org_name=f"UpB-{uuid.uuid4().hex[:6]}")

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=org_a["token"],
        json_body={"name": "Upload Target", "description": "isolated"},
    )
    matter_id = r.json()["id"]

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=org_b["token"],
        files={"file": ("secret.txt", b"Org A confidential text.", "text/plain")},
        data={"confidentiality": "internal"},
    )
    assert r.status_code == 404
