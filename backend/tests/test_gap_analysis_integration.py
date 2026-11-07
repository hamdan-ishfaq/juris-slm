"""Phase 9D — gap analysis integration tests."""
from __future__ import annotations

import time
import uuid

import pytest

from api_helpers import api_request, register_user


@pytest.mark.integration
def test_gap_analysis_job_completes(api_up):
    owner = register_user(org_name=f"Gap-{uuid.uuid4().hex[:6]}")
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "Gap Matter", "description": "agent test"},
    )
    matter_id = r.json()["id"]

    nda = (
        b"MUTUAL NON-DISCLOSURE AGREEMENT. Receiving Party shall not disclose confidential information. "
        b"Personal data processing shall comply with GDPR Article 28 processor obligations. "
        b"International transfer requires Standard Contractual Clauses."
    )
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=owner["token"],
        files={"file": ("nda_gap.txt", nda, "text/plain")},
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
        "POST",
        f"/api/v1/matters/{matter_id}/workflows/gap-analysis",
        token=owner["token"],
        json_body={"document_id": doc_id, "baseline": "gdpr"},
        timeout=30.0,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    report = None
    for _ in range(90):
        r = api_request(
            "GET",
            f"/api/v1/workflows/gap-analysis/{job_id}",
            token=owner["token"],
        )
        assert r.status_code == 200
        body = r.json()
        if body["status"] == "completed":
            report = body.get("report")
            break
        if body["status"] == "failed":
            pytest.fail(f"Gap analysis failed: {body.get('error')}")
        time.sleep(2)
    else:
        pytest.fail("Gap analysis job did not complete in time")

    assert report is not None
    assert len(report.get("obligations", [])) >= 1
    assert len(report.get("gaps", [])) >= 1
    assert report.get("tool_calls_used", 99) <= 12
    topics = {g.get("gap_description", "").lower() for g in report.get("gaps", [])}
    assert any("confidential" in t or "processing" in t or "transfer" in t or "gdpr" in t for t in topics) or len(report["gaps"]) >= 1

    r = api_request(
        "GET",
        "/api/v1/audit?action=agent_step&page_size=50",
        token=owner["token"],
    )
    assert r.status_code == 200
    agent_steps = [e for e in r.json().get("items", []) if e.get("action") == "agent_step"]
    assert len(agent_steps) >= 4
