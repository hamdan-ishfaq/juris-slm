"""Phase 9B — legal hold integration tests."""
from __future__ import annotations

import uuid

import pytest

from api_helpers import api_request, register_user


def _create_matter(token: str, name: str = "Hold Matter") -> str:
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=token,
        json_body={"name": name, "description": "legal hold test"},
    )
    assert r.status_code == 200
    return r.json()["id"]


@pytest.mark.integration
def test_active_hold_blocks_matter_delete(api_up):
    owner = register_user(org_name=f"HoldOrg-{uuid.uuid4().hex[:6]}")
    matter_id = _create_matter(owner["token"])

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/legal-hold",
        token=owner["token"],
        json_body={"reason": "Regulatory investigation pending"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    r = api_request("DELETE", f"/api/v1/matters/{matter_id}", token=owner["token"])
    assert r.status_code == 409
    assert "legal hold" in r.json()["detail"].lower()


@pytest.mark.integration
def test_member_cannot_place_hold(api_up):
    owner = register_user(org_name=f"HoldMem-{uuid.uuid4().hex[:6]}")
    member = register_user()
    from api_helpers import assign_user_to_org_sync

    assign_user_to_org_sync(member["user_id"], owner["org_id"])
    matter_id = _create_matter(owner["token"])

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/legal-hold",
        token=member["token"],
        json_body={"reason": "Should fail"},
    )
    assert r.status_code == 403


@pytest.mark.integration
def test_hold_and_release_in_audit_csv(api_up):
    owner = register_user(org_name=f"HoldAud-{uuid.uuid4().hex[:6]}")
    matter_id = _create_matter(owner["token"])

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/legal-hold",
        token=owner["token"],
        json_body={"reason": "DPO preservation order"},
    )
    hold_id = r.json()["id"]

    r = api_request(
        "DELETE",
        f"/api/v1/matters/{matter_id}/legal-hold/{hold_id}",
        token=owner["token"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "released"

    r = api_request("GET", "/api/v1/audit/export", token=owner["token"])
    assert r.status_code == 200
    csv_text = r.text
    assert "legal_hold_place" in csv_text
    assert "legal_hold_release" in csv_text


@pytest.mark.integration
def test_release_allows_matter_delete(api_up):
    owner = register_user(org_name=f"HoldRel-{uuid.uuid4().hex[:6]}")
    matter_id = _create_matter(owner["token"])

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/legal-hold",
        token=owner["token"],
        json_body={"reason": "Temporary hold"},
    )
    hold_id = r.json()["id"]

    api_request("DELETE", f"/api/v1/matters/{matter_id}/legal-hold/{hold_id}", token=owner["token"])

    r = api_request("DELETE", f"/api/v1/matters/{matter_id}", token=owner["token"])
    assert r.status_code == 200


@pytest.mark.integration
def test_document_hold_blocks_delete(api_up):
    owner = register_user(org_name=f"DocHold-{uuid.uuid4().hex[:6]}")
    matter_id = _create_matter(owner["token"])

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=owner["token"],
        files={"file": ("hold_doc.txt", b"Contract under hold.", "text/plain")},
        data={"confidentiality": "internal"},
    )
    doc_id = r.json()["id"]

    r = api_request(
        "POST",
        f"/api/v1/documents/{doc_id}/legal-hold",
        token=owner["token"],
        json_body={"reason": "Single document preservation"},
    )
    assert r.status_code == 200

    r = api_request("DELETE", f"/api/v1/matters/{matter_id}/documents/{doc_id}", token=owner["token"])
    assert r.status_code == 409
