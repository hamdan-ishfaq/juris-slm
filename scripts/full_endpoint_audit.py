#!/usr/bin/env python3
"""Rigorous audit of every backend route + frontend path cross-check."""
from __future__ import annotations

import json
import re
import sys
import time
import uuid
from pathlib import Path

import httpx

API = "http://localhost:8002"
EMAIL = "devmaster@example.com"
PASSWORD = "DevMasterPass123!"
ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"
REPORT = ROOT / "eval" / "reports" / "full_endpoint_audit.json"

# All backend routes (method, path template, auth, smoke callable name)
BACKEND_ROUTES: list[dict] = [
    {"method": "GET", "path": "/health", "auth": False},
    {"method": "GET", "path": "/api/v1/config/branding", "auth": False},
    {"method": "GET", "path": "/api/v1/auth/sso/status", "auth": False},
    {"method": "POST", "path": "/api/v1/auth/login", "auth": False},
    {"method": "GET", "path": "/api/v1/auth/me", "auth": True},
    {"method": "POST", "path": "/api/v1/auth/refresh", "auth": False},
    {"method": "GET", "path": "/api/v1/status", "auth": True},
    {"method": "GET", "path": "/api/v1/threads", "auth": True},
    {"method": "POST", "path": "/api/v1/threads", "auth": True},
    {"method": "GET", "path": "/api/v1/matters", "auth": True},
    {"method": "POST", "path": "/api/v1/matters", "auth": True},
    {"method": "GET", "path": "/api/v1/clause-library", "auth": True},
    {"method": "POST", "path": "/api/v1/clause-library", "auth": True},
    {"method": "GET", "path": "/api/v1/corpus/stats", "auth": True},
    {"method": "GET", "path": "/api/v1/audit", "auth": True},
    {"method": "GET", "path": "/api/v1/audit/export", "auth": True},
    {"method": "GET", "path": "/api/v1/admin/users", "auth": True},
    {"method": "GET", "path": "/api/v1/admin/org", "auth": True},
    {"method": "GET", "path": "/api/v1/admin/sso", "auth": True},
    {"method": "GET", "path": "/api/v1/admin/eval-status", "auth": True},
    {"method": "GET", "path": "/api/v1/admin/corpus/sources", "auth": True},
    {"method": "POST", "path": "/api/v1/chat", "auth": True},
    {"method": "POST", "path": "/api/v1/feedback", "auth": True},
    {"method": "POST", "path": "/api/v1/export/audit", "auth": True},
    {"method": "POST", "path": "/api/v1/export/analyze-report", "auth": True},
    {"method": "POST", "path": "/api/v1/export/compare-report", "auth": True},
    # dynamic routes tested in context setup
]


def collect_frontend_paths() -> set[str]:
    paths: set[str] = set()
    pat = re.compile(r"""api\(\s*['"`]([^'"`]+)['"`]""")
    files = list(FRONTEND_SRC.rglob("*.js")) + list(FRONTEND_SRC.rglob("*.jsx"))
    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(text):
            p = m.group(1).split("?")[0]
            if p.startswith("/api"):
                paths.add(p)
    return paths


def normalize(path: str) -> str:
  return re.sub(r"\$\{[^}]+\}", "{id}", path)


def main() -> int:
    client = httpx.Client(base_url=API, timeout=120.0)
    results: list[dict] = []
    ctx: dict = {}

    def run(name: str, method: str, path: str, *, headers=None, json_body=None, files=None, data=None, expect=(200, 201, 204)):
        r = client.request(method, path, headers=headers, json=json_body, files=files, data=data)
        ok = r.status_code in expect
        results.append({
            "name": name,
            "method": method,
            "path": path,
            "status": r.status_code,
            "ok": ok,
            "detail": (r.text[:160] if not ok else "")[:160],
        })
        mark = "OK" if ok else "FAIL"
        print(f"[{mark}] {r.status_code} {method} {path}")
        return r

    # login
    r = run("health", "GET", "/health", expect=(200,))
    if not results[-1]["ok"]:
        return 1
    r = run("login", "POST", "/api/v1/auth/login", json_body={"email": EMAIL, "password": PASSWORD}, expect=(200,))
    token = r.json()["access_token"]
    refresh = r.json().get("refresh_token", "")
    h = {"Authorization": f"Bearer {token}"}

    for route in BACKEND_ROUTES:
        if route["path"] in ("/health", "/api/v1/auth/login"):
            continue
        hdrs = h if route.get("auth") else None
        body = None
        if route["path"] == "/api/v1/auth/refresh":
            body = {"refresh_token": refresh}
        if route["method"] == "POST" and route["path"] == "/api/v1/matters":
            body = {"name": f"Endpoint audit {uuid.uuid4().hex[:8]}", "description": "audit"}
        if route["path"] == "/api/v1/clause-library" and route["method"] == "POST":
            body = {"clause_type": "confidentiality", "title": "Audit", "body_text": "Shall keep confidential.", "jurisdiction": "eu"}
        if route["path"] == "/api/v1/chat":
            body = {"message": "GDPR Article 6 lawful basis?", "use_law_corpus": True}
        if route["path"] == "/api/v1/feedback":
            body = {"rating": "up", "question": "q", "answer": "a"}
        if route["path"] == "/api/v1/export/audit":
            body = {"format": "pdf", "question": "Q", "answer": "A", "sources": []}
        if route["path"] == "/api/v1/export/analyze-report":
            body = {"format": "markdown", "matter_id": str(ctx.get("matter_id", uuid.uuid4())), "question": "q", "answer": "a"}
        if route["path"] == "/api/v1/export/compare-report":
            body = {"format": "markdown", "matter_id": str(ctx.get("matter_id", uuid.uuid4())), "document_id": str(ctx.get("doc_id", uuid.uuid4())), "question": "q"}
        if route["path"] == "/api/v1/threads" and route["method"] == "POST":
            body = {"title": "audit thread"}
        run(route["path"], route["method"], route["path"], headers=hdrs, json_body=body)

    # contextual flows
    m = run("create_matter", "POST", "/api/v1/matters", headers=h, json_body={"name": f"Full audit {uuid.uuid4().hex[:6]}", "description": "x"}).json()
    ctx["matter_id"] = m["id"]
    fixture = ROOT / "frontend/e2e/fixtures/sample_nda.txt"
    up = run(
        "upload_doc",
        "POST",
        f"/api/v1/matters/{ctx['matter_id']}/documents",
        headers=h,
        files={"file": ("sample_nda.txt", fixture.read_bytes(), "text/plain")},
        data={"confidentiality": "internal"},
    ).json()
    ctx["doc_id"] = up["id"]
    for _ in range(40):
        st = client.get(f"/api/v1/matters/{ctx['matter_id']}/documents/{ctx['doc_id']}/status", headers=h).json()
        if st.get("status") in ("processed", "failed"):
            break
        time.sleep(2)

    dynamic = [
        ("list_docs", "GET", f"/api/v1/matters/{ctx['matter_id']}/documents"),
        ("doc_status", "GET", f"/api/v1/matters/{ctx['matter_id']}/documents/{ctx['doc_id']}/status"),
        ("graph_entities", "GET", f"/api/v1/matters/{ctx['matter_id']}/documents/{ctx['doc_id']}/graph-entities"),
        ("graph_edges", "GET", f"/api/v1/matters/{ctx['matter_id']}/documents/{ctx['doc_id']}/graph-edges"),
        ("graph_extract", "POST", f"/api/v1/matters/{ctx['matter_id']}/documents/{ctx['doc_id']}/graph-extract"),
        ("analyze", "POST", f"/api/v1/matters/{ctx['matter_id']}/analyze", {"document_id": ctx["doc_id"], "question": "Summarize"}),
        ("compare", "POST", f"/api/v1/matters/{ctx['matter_id']}/compare", {"document_id": ctx["doc_id"], "question": "GDPR"}),
        ("workspace_get", "GET", f"/api/v1/matters/{ctx['matter_id']}/documents/{ctx['doc_id']}/workspace"),
        ("deadlines_list", "GET", f"/api/v1/matters/{ctx['matter_id']}/deadlines"),
        ("legal_holds", "GET", f"/api/v1/matters/{ctx['matter_id']}/legal-holds"),
        ("gap_start", "POST", f"/api/v1/matters/{ctx['matter_id']}/workflows/gap-analysis", {"document_id": ctx["doc_id"], "baseline": "gdpr"}),
    ]
    job_id = None
    for item in dynamic:
        name, method, path = item[0], item[1], item[2]
        body = item[3] if len(item) > 3 else None
        r = run(name, method, path, headers=h, json_body=body)
        if name == "gap_start" and r.status_code == 200:
            job_id = r.json().get("job_id")
    if job_id:
        run("gap_status", "GET", f"/api/v1/workflows/gap-analysis/{job_id}", headers=h)

  # frontend cross-check
    fe_paths = sorted(collect_frontend_paths())
    backend_templates = {normalize(r["path"]) for r in BACKEND_ROUTES}
    # add dynamic templates
    backend_templates.update({
        "/api/v1/matters/{id}/documents",
        "/api/v1/matters/{id}/documents/{id}/status",
        "/api/v1/matters/{id}/documents/{id}/graph-entities",
        "/api/v1/matters/{id}/documents/{id}/graph-edges",
        "/api/v1/matters/{id}/documents/{id}/graph-extract",
        "/api/v1/matters/{id}/analyze",
        "/api/v1/matters/{id}/compare",
        "/api/v1/matters/{id}/compare-clause",
        "/api/v1/matters/{id}/documents/{id}/workspace",
        "/api/v1/matters/{id}/documents/{id}/export/docx",
        "/api/v1/matters/{id}/documents/{id}/annotations",
        "/api/v1/matters/{id}/workflows/gap-analysis",
        "/api/v1/workflows/gap-analysis/{id}",
        "/api/v1/matters/{id}/deadlines",
        "/api/v1/matters/{id}/deadlines/{id}",
        "/api/v1/matters/{id}/legal-hold",
        "/api/v1/matters/{id}/legal-holds",
        "/api/v1/matters/{id}/legal-hold/{id}",
        "/api/v1/matters/{id}/documents/bulk",
        "/api/v1/matters/{id}/documents/bulk-files",
        "/api/v1/matters/{id}/members",
        "/api/v1/threads/{id}/messages",
        "/api/v1/chat/jobs/{id}",
        "/api/v1/chat/stream",
        "/api/v1/chat/async",
        "/api/v1/clause-library/{id}",
        "/api/v1/admin/users/{id}/role",
        "/api/v1/admin/users/{id}/revoke-sessions",
        "/api/v1/admin/corpus/upload",
        "/api/v1/admin/corpus/sources/{id}/ingest",
        "/api/v1/admin/run-eval",
        "/api/v1/admin/scim-token",
        "/api/v1/audit",
    })

    def fe_matches_backend(fe: str) -> bool:
        n = normalize(fe)
        if n in backend_templates:
            return True
        for bt in backend_templates:
            if re.fullmatch(bt.replace("{id}", "[^/]+"), n):
                return True
        return False

    orphan_fe = [p for p in fe_paths if not fe_matches_backend(p)]

    failed = [x for x in results if not x["ok"]]
    out = {
        "total_tests": len(results),
        "failed": len(failed),
        "frontend_paths": fe_paths,
        "frontend_orphan_paths": orphan_fe,
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=2))
    print(f"\n{len(results)-len(failed)}/{len(results)} endpoint tests passed")
    if orphan_fe:
        print("Frontend paths with no obvious backend route:")
        for p in orphan_fe:
            print(f"  - {p}")
    else:
        print("All frontend API paths match backend routes.")
    print(f"Report: {REPORT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
