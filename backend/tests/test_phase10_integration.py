"""Phase 10 — integration tests for production features."""
from __future__ import annotations

import time
import uuid

import pytest

from api_helpers import api_request, register_user


@pytest.mark.integration
def test_branding_config_public(api_up):
    r = api_request("GET", "/api/v1/config/branding")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "brand_name" in body
    assert "brand_primary_color" in body
    assert body["brand_name"]


@pytest.mark.integration
def test_refresh_token_rotation(api_up):
    owner = register_user(org_name=f"Refresh-{uuid.uuid4().hex[:6]}")
    login = api_request(
        "POST",
        "/api/v1/auth/login",
        json_body={"email": owner["email"], "password": owner["password"]},
    )
    assert login.status_code == 200, login.text
    data = login.json()
    refresh = data.get("refresh_token")
    assert refresh, "login should return refresh_token"

    r = api_request(
        "POST",
        "/api/v1/auth/refresh",
        json_body={"refresh_token": refresh},
    )
    assert r.status_code == 200, r.text
    rotated = r.json()
    assert rotated["access_token"]
    assert rotated["refresh_token"]
    assert rotated["refresh_token"] != refresh

    # Old refresh token must not work
    r2 = api_request(
        "POST",
        "/api/v1/auth/refresh",
        json_body={"refresh_token": refresh},
    )
    assert r2.status_code == 401


@pytest.mark.integration
def test_clause_library_crud(api_up):
    owner = register_user(org_name=f"Clause-{uuid.uuid4().hex[:6]}")
    token = owner["token"]

    r = api_request(
        "POST",
        "/api/v1/clause-library",
        token=token,
        json_body={
            "clause_type": "confidentiality",
            "title": "Standard NDA",
            "body_text": "Receiving Party shall not disclose Confidential Information.",
            "jurisdiction": "eu",
        },
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]

    r = api_request("GET", "/api/v1/clause-library", token=token)
    assert r.status_code == 200
    assert any(c["id"] == item_id for c in r.json())

    r = api_request(
        "PATCH",
        f"/api/v1/clause-library/{item_id}",
        token=token,
        json_body={"title": "Updated NDA"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Updated NDA"

    r = api_request("DELETE", f"/api/v1/clause-library/{item_id}", token=token)
    assert r.status_code == 200


@pytest.mark.integration
def test_corpus_admin_upload_and_reingest(api_up):
    owner = register_user(org_name=f"Corpus-{uuid.uuid4().hex[:6]}")
    token = owner["token"]

    law_text = (
        "Article 5 GDPR — Personal data shall be processed lawfully, fairly and transparently. "
        "Article 6 — Processing is lawful only if a legal basis applies."
    )
    r = api_request(
        "POST",
        "/api/v1/admin/corpus/upload",
        token=token,
        files={"file": ("gdpr_snippet.txt", law_text.encode(), "text/plain")},
        data={"title": "GDPR Snippet", "jurisdiction": "eu", "slug": f"gdpr-{uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 200, r.text
    source_id = r.json()["id"]

    r = api_request("GET", "/api/v1/admin/corpus/sources", token=token)
    assert r.status_code == 200
    assert source_id in [s["id"] for s in r.json()]

    r = api_request("POST", f"/api/v1/admin/corpus/sources/{source_id}/ingest", token=token)
    assert r.status_code == 200
    assert r.json()["status"] in ("pending", "processing", "processed")


@pytest.mark.integration
def test_revoke_sessions_invalidates_refresh(api_up):
    from api_helpers import assign_user_to_org_sync

    owner = register_user(org_name=f"Revoke-{uuid.uuid4().hex[:6]}")
    member = register_user()
    assign_user_to_org_sync(member["user_id"], owner["org_id"])
    login = api_request(
        "POST",
        "/api/v1/auth/login",
        json_body={"email": member["email"], "password": member["password"]},
    )
    refresh = login.json().get("refresh_token")
    assert refresh

    r = api_request(
        "POST",
        f"/api/v1/admin/users/{member['user_id']}/revoke-sessions",
        token=owner["token"],
    )
    assert r.status_code == 200, r.text
    assert r.json().get("revoked", 0) >= 1

    r2 = api_request("POST", "/api/v1/auth/refresh", json_body={"refresh_token": refresh})
    assert r2.status_code == 401


@pytest.mark.integration
def test_compare_clause_against_library(api_up):
    owner = register_user(org_name=f"CmpClause-{uuid.uuid4().hex[:6]}")
    token = owner["token"]

    r = api_request(
        "POST",
        "/api/v1/clause-library",
        token=token,
        json_body={
            "clause_type": "confidentiality",
            "title": "Firm NDA",
            "body_text": "Receiving Party shall not disclose Confidential Information for five years.",
            "jurisdiction": "eu",
        },
    )
    clause_id = r.json()["id"]

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=token,
        json_body={"name": "Compare Clause Matter", "description": "test"},
    )
    matter_id = r.json()["id"]

    nda = b"The parties agree to keep information secret. No disclosure without consent."
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=token,
        files={"file": ("nda_cmp.txt", nda, "text/plain")},
        data={"confidentiality": "internal"},
    )
    doc_id = r.json()["id"]

    for _ in range(45):
        st = api_request("GET", f"/api/v1/matters/{matter_id}/documents/{doc_id}/status", token=token)
        if st.json().get("status") == "processed":
            break
        time.sleep(2)
    else:
        pytest.skip("Document not processed in time")

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/compare-clause",
        token=token,
        json_body={"document_id": doc_id, "clause_library_id": clause_id},
        timeout=120.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("comparison_result")
    assert body.get("deviation_flag") in ("aligned", "deviates")


@pytest.mark.integration
def test_metrics_endpoint(api_up):
    r = api_request("GET", "/metrics")
    assert r.status_code == 200
    assert "juris_http_requests" in r.text or "# HELP" in r.text or "juris_up" in r.text


@pytest.mark.integration
def test_matter_deadlines_crud(api_up):
    owner = register_user(org_name=f"DL-{uuid.uuid4().hex[:6]}")
    token = owner["token"]
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=token,
        json_body={"name": "Deadline Matter", "description": "test"},
    )
    matter_id = r.json()["id"]
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/deadlines",
        token=token,
        json_body={"title": "Filing deadline", "due_date": "2026-12-31"},
    )
    assert r.status_code == 201, r.text
    dl_id = r.json()["id"]
    r = api_request("GET", f"/api/v1/matters/{matter_id}/deadlines", token=token)
    assert any(d["id"] == dl_id for d in r.json())
    r = api_request(
        "PATCH",
        f"/api/v1/matters/{matter_id}/deadlines/{dl_id}",
        token=token,
        json_body={"status": "done"},
    )
    assert r.json()["status"] == "done"


@pytest.mark.integration
def test_bulk_files_upload(api_up):
    owner = register_user(org_name=f"BulkF-{uuid.uuid4().hex[:6]}")
    token = owner["token"]
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=token,
        json_body={"name": "Bulk Files", "description": "test"},
    )
    matter_id = r.json()["id"]
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents/bulk-files",
        token=token,
        files=[
            ("files", ("a.txt", b"Contract A confidentiality clause.", "text/plain")),
            ("files", ("b.txt", b"Contract B liability cap section.", "text/plain")),
        ],
        data={"confidentiality": "internal"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 2


@pytest.mark.integration
def test_status_includes_hardware_block(api_up):
    owner = register_user(org_name=f"HW-{uuid.uuid4().hex[:6]}")
    r = api_request("GET", "/api/v1/status", token=owner["token"])
    assert r.status_code == 200
    hw = r.json().get("hardware")
    assert hw is not None
    assert "embedding_device" in hw
    assert "cuda_available" in hw


@pytest.mark.integration
def test_async_chat_job_completes(api_up):
    owner = register_user(org_name=f"ChatAsync-{uuid.uuid4().hex[:6]}")
    token = owner["token"]

    r = api_request(
        "POST",
        "/api/v1/chat/async",
        token=token,
        json_body={"message": "What is GDPR Article 5?", "use_law_corpus": True, "use_hyde": False},
        timeout=30.0,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    answer = None
    for _ in range(90):
        r = api_request("GET", f"/api/v1/chat/jobs/{job_id}", token=token)
        assert r.status_code == 200
        body = r.json()
        if body["status"] == "completed":
            answer = body.get("answer")
            break
        if body["status"] == "failed":
            pytest.fail(f"Async chat failed: {body.get('error')}")
        time.sleep(2)
    else:
        pytest.skip("Async chat job did not complete in time (LLM may be unavailable)")

    assert answer and len(answer) > 20
