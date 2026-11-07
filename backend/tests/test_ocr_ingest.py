"""Phase 10B — OCR ingest integration tests."""
from __future__ import annotations

import uuid

import pytest

from api_helpers import api_request, register_user


@pytest.mark.integration
def test_document_status_reports_ocr_and_processed(api_up):
    owner = register_user(org_name=f"OCR-{uuid.uuid4().hex[:6]}")
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "OCR Matter", "description": "ocr status test"},
    )
    matter_id = r.json()["id"]
    content = b"CONFIDENTIALITY. Receiving Party shall not disclose Confidential Information for five years."
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=owner["token"],
        files={"file": ("nda_ocr.txt", content, "text/plain")},
        data={"confidentiality": "internal"},
    )
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]

    import time

    status = None
    for _ in range(45):
        r = api_request(
            "GET",
            f"/api/v1/matters/{matter_id}/documents/{doc_id}/status",
            token=owner["token"],
        )
        assert r.status_code == 200
        status = r.json()
        if status.get("status") in ("processed", "failed"):
            break
        time.sleep(2)
    assert status is not None
    assert status["status"] == "processed"
    assert "ocr_used" in status


@pytest.mark.integration
def test_eml_upload_parses(api_up):
    owner = register_user(org_name=f"EML-{uuid.uuid4().hex[:6]}")
    r = api_request(
        "POST",
        "/api/v1/matters",
        token=owner["token"],
        json_body={"name": "EML Matter", "description": "eml test"},
    )
    matter_id = r.json()["id"]
    eml = (
        b"From: counsel@firm.example\r\n"
        b"To: client@corp.example\r\n"
        b"Subject: NDA review\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"Please review the mutual confidentiality obligations in the attached NDA draft."
    )
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_id}/documents",
        token=owner["token"],
        files={"file": ("thread.eml", eml, "message/rfc822")},
        data={"confidentiality": "internal"},
    )
    assert r.status_code == 200, r.text
