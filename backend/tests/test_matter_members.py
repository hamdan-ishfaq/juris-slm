"""Matter member invite/remove integration tests — Phase 1."""
from __future__ import annotations

import uuid

import pytest

from api_helpers import api_request, register_user, assign_user_to_org_sync as assign_user_to_org


@pytest.mark.integration
def test_cross_org_invite_rejected(api_up):
    owner = register_user(org_name=f"Firm-{uuid.uuid4().hex[:6]}")
    outsider = register_user()

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "Shared Matter", "description": "test"},
    )
    assert r.status_code == 200
    matter_id = r.json()["id"]

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/members",
        token=owner["token"],
        json_body={"email": outsider["email"], "role": "viewer"},
    )
    assert r.status_code == 400


@pytest.mark.integration
def test_invite_viewer_then_remove(api_up):
    owner = register_user(org_name=f"Collab-{uuid.uuid4().hex[:6]}")
    collaborator = register_user()
    assign_user_to_org(collaborator["user_id"], owner["org_id"])

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "Collab Matter", "description": "test"},
    )
    matter_id = r.json()["id"]

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/members",
        token=owner["token"],
        json_body={"email": collaborator["email"], "role": "viewer"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"

    r = api_request("GET", f"/api/v1/matters/{matter_id}", token=collaborator["token"])
    assert r.status_code == 200

    r = api_request(
        "DELETE",
        f"/api/v1/matters/{matter_id}/members/{collaborator['user_id']}",
        token=owner["token"],
    )
    assert r.status_code == 200

    r = api_request("GET", f"/api/v1/matters/{matter_id}", token=collaborator["token"])
    assert r.status_code == 403


@pytest.mark.integration
def test_viewer_cannot_upload(api_up):
    owner = register_user(org_name=f"ViewerOrg-{uuid.uuid4().hex[:6]}")
    viewer = register_user()
    assign_user_to_org(viewer["user_id"], owner["org_id"])

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "Viewer Matter", "description": "test"},
    )
    matter_id = r.json()["id"]

    api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/members",
        token=owner["token"],
        json_body={"email": viewer["email"], "role": "viewer"},
    )

    nda = b"NDA between Party A and Party B."
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=viewer["token"],
        files={"file": ("nda.txt", nda, "text/plain")},
        data={"confidentiality": "internal"},
    )
    assert r.status_code == 403
