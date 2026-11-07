"""Phase 9F — contract workspace integration tests."""
from __future__ import annotations

import time
import uuid

import pytest

from api_helpers import api_request, register_user, assign_user_to_org_sync as assign_user_to_org


@pytest.mark.integration
def test_contract_workspace_save_and_export(api_up):
    owner = register_user(org_name=f"Contract-{uuid.uuid4().hex[:6]}")
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "Contract Matter", "description": "editor test"},
    )
    matter_id = r.json()["id"]

    nda = (
        b"1. CONFIDENTIALITY\nReceiving Party shall not disclose confidential information.\n\n"
        b"2. DATA PROCESSING\nProcessor shall comply with GDPR Article 28.\n"
    )
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=owner["token"],
        files={"file": ("nda_editor.txt", nda, "text/plain")},
        data={"confidentiality": "internal"},
    )
    doc_id = r.json()["id"]

    for _ in range(60):
        st = api_request(
            "GET",
            f"/api/v1/matters/{matter_id}/documents/{doc_id}/status",
            token=owner["token"],
        )
        if st.json().get("status") == "processed":
            break
        time.sleep(2)
    else:
        pytest.skip("Document not processed in time")

    r = api_request(
        "GET",
        f"/api/v1/matters/{matter_id}/documents/{doc_id}/workspace",
        token=owner["token"],
    )
    assert r.status_code == 200
    ws = r.json()
    assert ws["version_number"] == 1
    assert len(ws.get("clauses", [])) >= 1

    edited = ws["content_text"] + "\n\n3. TERMINATION\nEither party may terminate with notice."
    r = api_request(
        "PUT",
        f"/api/v1/matters/{matter_id}/documents/{doc_id}/workspace",
        token=owner["token"],
        json_body={"content_text": edited, "expected_version_number": 1},
    )
    assert r.status_code == 200
    assert r.json()["version_number"] == 2

    r = api_request(
        "GET",
        f"/api/v1/matters/{matter_id}/documents/{doc_id}/versions",
        token=owner["token"],
    )
    assert r.status_code == 200
    assert len(r.json()) >= 2

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents/{doc_id}/annotations",
        token=owner["token"],
        json_body={"clause_id": "clause-1", "comment": "Review confidentiality scope"},
    )
    assert r.status_code == 200

    r = api_request(
        "GET",
        f"/api/v1/matters/{matter_id}/documents/{doc_id}/export/docx",
        token=owner["token"],
    )
    assert r.status_code == 200
    assert "wordprocessingml" in r.headers.get("content-type", "")
    assert len(r.content) > 1000

    r = api_request(
        "GET",
        "/api/v1/audit?action=document_edit&page_size=10",
        token=owner["token"],
    )
    assert r.status_code == 200
    edits = [e for e in r.json().get("items", []) if e.get("action") == "document_edit"]
    assert len(edits) >= 1


@pytest.mark.integration
def test_viewer_cannot_save_workspace(api_up):
    owner = register_user(org_name=f"ViewOnly-{uuid.uuid4().hex[:6]}")
    viewer = register_user()
    r = api_request("POST", "/api/v1/matters", token=owner["token"], json_body={"name": "M", "description": "d"})
    matter_id = r.json()["id"]
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=owner["token"],
        files={"file": ("simple.txt", b"1. TEST\nBody text.", "text/plain")},
        data={"confidentiality": "internal"},
    )
    doc_id = r.json()["id"]
    assign_user_to_org(viewer["user_id"], owner["org_id"])
    api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/members",
        token=owner["token"],
        json_body={"email": viewer["email"], "role": "viewer"},
    )
    r = api_request(
        "PUT",
        f"/api/v1/matters/{matter_id}/documents/{doc_id}/workspace",
        token=viewer["token"],
        json_body={"content_text": "tampered"},
    )
    assert r.status_code == 403
