"""H6 end to end: upload real dev-split LegalBench documents through the API and ask their questions.

Run on the host from the repo folder, with .env exported: .venv/bin/python <this file>
Uses dev documents only. Also reports section sizes for the project's own contract fixtures.
"""
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, "eval/legalbench")
sys.path.insert(0, "scripts")
sys.path.insert(0, "backend/src")
import legalbench as lb
from eval_common import API_BASE, create_matter, login_dev_master, request_with_auth, wait_document_ready
from services.advanced_chunking import hierarchical_chunk

DOCS = [
    "privacy_qa/Keep.txt",
    "privacy_qa/Groupon.txt",
    "contractnli/NDA_ResConnect.txt",
    "cuad/Loop Industries, Inc. - Marketing Agreement.txt",
    "maud/Select_Bancorp_Inc_First_Bancorp.txt",
]
PER_DOC = 4
CAP = 6000

token = login_dev_master()["token"]
matter = create_matter(token, "H6 LegalBench dev upload")
mini = lb.load_mini()
rows = []
for path in DOCS:
    body = (lb.CORPUS / path).read_text()
    items = hierarchical_chunk(body)
    over = sum(len(i.get("parent_content") or "") > CAP for i in items)
    response = request_with_auth(
        "POST",
        f"{API_BASE}/api/v1/matters/{matter}/documents",
        token=token,
        # The upload filter rejects commas (a separate bug), so names are simplified here.
        files={"file": (re.sub(r"[^A-Za-z0-9._-]", "_", Path(path).name), body.encode(), "text/plain")},
        data={"confidentiality": "internal"},
        timeout=120.0,
    )
    response.raise_for_status()
    document_id = str(response.json()["id"])
    ready = wait_document_ready(token, matter, document_id, timeout=900.0)
    questions = [t for t in mini if t["snippets"][0]["file_path"] == path][:PER_DOC]
    for test in questions:
        started = time.perf_counter()
        # /analyze is the single-document route. /chat has no document_id field and searches
        # every document the user can access.
        reply = request_with_auth(
            "POST",
            f"{API_BASE}/api/v1/matters/{matter}/analyze",
            token=token,
            json={"document_id": document_id, "question": test["query"]},
            timeout=1200.0,
        )
        data = reply.json() if reply.status_code == 200 else {}
        answer = data.get("answer", "")
        rows.append(
            {
                "document": path,
                "ready": ready,
                "chunks": len(items),
                "chunks_with_parent_over_cap": over,
                "qid": test["qid"],
                "http": reply.status_code,
                "seconds": round(time.perf_counter() - started, 1),
                "sources": len(data.get("sources", [])),
                "answer_chars": len(answer),
                "no_context_reply": "No relevant context" in answer,
                "insufficient_reply": "Insufficient relevant context" in answer,
                "answer_start": answer[:160],
            }
        )
        print(json.dumps(rows[-1])[:330], flush=True)

fixtures = {}
for fixture in sorted(Path("eval/fixtures").glob("*.txt")):
    items = hierarchical_chunk(fixture.read_text())
    fixtures[fixture.name] = {
        "chars": len(fixture.read_text()),
        "largest_parent": max(len(i.get("parent_content") or "") for i in items),
    }
summary = {
    "questions": len(rows),
    "no_context_replies": sum(r["no_context_reply"] for r in rows),
    "insufficient_replies": sum(r["insufficient_reply"] for r in rows),
    "http": dict(Counter(r["http"] for r in rows)),
    "project_fixtures": fixtures,
}
Path(__file__).with_suffix(".json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
print(json.dumps(summary, indent=1))
