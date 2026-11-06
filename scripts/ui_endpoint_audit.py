#!/usr/bin/env python3
"""Hit every API route the UI uses; report failures."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import httpx

API = os.environ.get("API_URL", "http://localhost:8002")
EMAIL = os.environ.get("DEV_EMAIL", "devmaster@example.com")
PASSWORD = os.environ.get("DEV_PASSWORD", "DevMasterPass123!")

results: list[dict] = []


def record(name: str, method: str, path: str, status: int, detail: str = ""):
    ok = 200 <= status < 300 or status == 204
    results.append({"name": name, "method": method, "path": path, "status": status, "ok": ok, "detail": detail[:200]})
    mark = "OK" if ok else "FAIL"
    print(f"[{mark}] {status:3d} {method:6s} {path}  {detail[:80]}")


def main() -> int:
    client = httpx.Client(base_url=API, timeout=120.0)

    r = client.get("/health")
    record("health", "GET", "/health", r.status_code)
    if not r.is_success:
        print("API down")
        return 1

    r = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    record("login", "POST", "/api/v1/auth/login", r.status_code, r.text[:80] if not r.is_success else "")
    if not r.is_success:
        return 1
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    for path in [
        "/api/v1/auth/me",
        "/api/v1/status",
        "/api/v1/threads",
        "/api/v1/matters",
        "/api/v1/clause-library",
        "/api/v1/corpus/stats",
        "/api/v1/audit?page=1&page_size=10",
        "/api/v1/admin/users",
        "/api/v1/admin/org",
        "/api/v1/admin/sso",
        "/api/v1/admin/corpus/sources",
        "/api/v1/config/branding",
        "/api/v1/auth/sso/status",
    ]:
        r = client.get(path, headers=h if path.startswith("/api/v1/") and "branding" not in path and "sso/status" not in path else None)
        hdrs = h if "auth/" not in path and "config/" not in path else {}
        if path in ("/api/v1/config/branding", "/api/v1/auth/sso/status"):
            r = client.get(path)
        else:
            r = client.get(path, headers=h)
        record(path.split("?")[0].split("/")[-1], "GET", path, r.status_code, r.text[:80] if not r.is_success else "")

    # Create matter + upload sample doc
    r = client.post("/api/v1/matters", headers=h, json={"name": f"UI Audit {uuid.uuid4().hex[:8]}", "description": "audit"})
    record("create_matter", "POST", "/api/v1/matters", r.status_code)
    matter_id = r.json().get("id") if r.is_success else None

    doc_id = None
    if matter_id:
        sample = Path(__file__).resolve().parents[1] / "frontend/e2e/fixtures/sample_nda.txt"
        if sample.exists():
            with sample.open("rb") as f:
                r = client.post(
                    f"/api/v1/matters/{matter_id}/documents",
                    headers=h,
                    files={"file": ("sample_nda.txt", f, "text/plain")},
                    data={"confidentiality": "internal"},
                )
            record("upload_doc", "POST", f"/api/v1/matters/{matter_id}/documents", r.status_code, r.text[:80] if not r.is_success else "")
            if r.is_success:
                doc_id = r.json().get("id")
                for _ in range(30):
                    st = client.get(f"/api/v1/matters/{matter_id}/documents/{doc_id}/status", headers=h)
                    if st.json().get("status") in ("processed", "failed"):
                        break
                    import time
                    time.sleep(2)

        r = client.get(f"/api/v1/matters/{matter_id}/documents", headers=h)
        record("list_docs", "GET", f"/api/v1/matters/{matter_id}/documents", r.status_code)

        r = client.post(f"/api/v1/matters/{matter_id}/deadlines", headers=h, json={"title": "Audit deadline", "due_date": "2026-12-31"})
        record("add_deadline", "POST", f"/api/v1/matters/{matter_id}/deadlines", r.status_code)

        r = client.get(f"/api/v1/matters/{matter_id}/deadlines", headers=h)
        record("list_deadlines", "GET", f"/api/v1/matters/{matter_id}/deadlines", r.status_code)

        r = client.get(f"/api/v1/matters/{matter_id}/legal-holds", headers=h)
        record("legal_holds", "GET", f"/api/v1/matters/{matter_id}/legal-holds", r.status_code)

    if matter_id and doc_id:
        for ep in ["graph-entities", "graph-edges"]:
            r = client.get(f"/api/v1/matters/{matter_id}/documents/{doc_id}/{ep}", headers=h)
            body = r.json() if r.is_success else {}
            detail = f"nodes/edges={len(body.get('entities', body.get('edges', [])))}" if r.is_success else r.text[:80]
            record(ep, "GET", f".../{ep}", r.status_code, detail)

        r = client.post(
            f"/api/v1/matters/{matter_id}/analyze",
            headers=h,
            json={"document_id": doc_id, "question": "Summarize confidentiality obligations"},
        )
        record("analyze", "POST", f"/api/v1/matters/{matter_id}/analyze", r.status_code, r.text[:80] if not r.is_success else "")

        r = client.post(
            f"/api/v1/matters/{matter_id}/compare",
            headers=h,
            json={"document_id": doc_id, "question": "Compare against GDPR"},
        )
        record("compare", "POST", f"/api/v1/matters/{matter_id}/compare", r.status_code, r.text[:80] if not r.is_success else "")

        r = client.get(f"/api/v1/matters/{matter_id}/documents/{doc_id}/workspace", headers=h)
        record("workspace", "GET", ".../workspace", r.status_code, r.text[:80] if not r.is_success else "")

    # Chat
    r = client.post("/api/v1/chat", headers=h, json={"message": "What is GDPR Article 6?", "use_law_corpus": True})
    record("chat", "POST", "/api/v1/chat", r.status_code, r.text[:80] if not r.is_success else "")

    # Exports (common 500 sources)
    for fmt in ("markdown", "pdf"):
        r = client.post(
            "/api/v1/export/audit",
            headers=h,
            json={
                "format": fmt,
                "question": "What is GDPR Article 6?",
                "answer": "Lawful processing requires a legal basis under Article 6(1).",
                "sources": [{"label": "GDPR Art 6", "rerank_score": 0.5}],
            },
        )
        record(f"export_audit_{fmt}", "POST", "/api/v1/export/audit", r.status_code, r.text[:80] if not r.is_success else f"{len(r.content)} bytes")

    r = client.post(
        "/api/v1/export/analyze-report",
        headers=h,
        json={"format": "markdown", "matter_id": matter_id, "document_id": doc_id, "question": "q", "answer": "a", "filename": "test.txt"},
    )
    record("export_analyze", "POST", "/api/v1/export/analyze-report", r.status_code, r.text[:80] if not r.is_success else "")

    r = client.get("/api/v1/audit/export", headers=h)
    record("audit_csv", "GET", "/api/v1/audit/export", r.status_code, f"{len(r.content)} bytes" if r.is_success else r.text[:80])

    r = client.post("/api/v1/feedback", headers=h, json={"rating": "up", "question": "q", "answer": "a"})
    record("feedback", "POST", "/api/v1/feedback", r.status_code)

    r = client.post("/api/v1/clause-library", headers=h, json={"clause_type": "confidentiality", "title": "Audit clause", "body_text": "Party shall keep information confidential.", "jurisdiction": "eu"})
    record("clause_create", "POST", "/api/v1/clause-library", r.status_code)

    failed = [x for x in results if not x["ok"]]
    out = Path(__file__).resolve().parents[1] / "eval/reports/ui_endpoint_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"total": len(results), "failed": len(failed), "results": results}, indent=2))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed — report: {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
