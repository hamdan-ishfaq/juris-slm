"""Phase 9A — cross-org vector retrieval isolation."""
from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from api_helpers import api_request, register_user
from db import User, async_session_factory
from deps import get_accessible_document_ids
from services.embeddings import embed_texts
from services.vector_store import search_similar


@pytest.mark.integration
def test_org_b_never_retrieves_org_a_chunks(api_up):
    async def _run() -> None:
        org_a = register_user(org_name=f"RetA-{uuid.uuid4().hex[:6]}")
        org_b = register_user(org_name=f"RetB-{uuid.uuid4().hex[:6]}")
        assert org_a["org_id"] != org_b["org_id"]

        r = api_request(
            "POST",
            "/api/v1/matters",
            token=org_a["token"],
            json_body={"name": "Retrieval Org A", "description": "isolated"},
        )
        matter_a = r.json()["id"]

        marker = f"ORG_ISO_{uuid.uuid4().hex[:12]}"
        content = f"{marker} Cross-org isolation retrieval test payload."
        r = api_request(
            "POST",
            f"/api/v1/matters/{matter_a}/documents",
            token=org_a["token"],
            files={"file": ("org_a_doc.txt", content.encode(), "text/plain")},
            data={"confidentiality": "internal"},
        )
        assert r.status_code == 200
        doc_a = uuid.UUID(r.json()["id"])

        for _ in range(60):
            st = api_request(
                "GET",
                f"/api/v1/matters/{matter_a}/documents/{doc_a}/status",
                token=org_a["token"],
            )
            if st.json().get("status") == "processed":
                break
            time.sleep(2)
        else:
            pytest.skip("Document not processed in time — worker may be down")

        async with async_session_factory() as db:
            user_b_row = await db.get(User, uuid.UUID(org_b["user_id"]))
            assert user_b_row is not None
            accessible_b = await get_accessible_document_ids(db, user_b_row)
            assert doc_a not in accessible_b

            query_vec = embed_texts([marker])[0]
            hits = await search_similar(
                db,
                query_vec,
                top_k=10,
                accessible_document_ids=accessible_b,
                include_law_corpus=False,
                user_role=user_b_row.role,
                org_id=user_b_row.org_id,
            )
            leaked = [h for h in hits if marker in (h.get("content") or "")]
            assert len(leaked) == 0, f"Org B retrieval leaked Org A chunks: {leaked}"

    asyncio.run(_run())


@pytest.mark.integration
def test_cross_org_analyze_blocked(api_up):
    org_a = register_user(org_name=f"AnA-{uuid.uuid4().hex[:6]}")
    org_b = register_user(org_name=f"AnB-{uuid.uuid4().hex[:6]}")

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=org_a["token"],
        json_body={"name": "Analyze Target", "description": "isolated"},
    )
    matter_a = r.json()["id"]

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_a}/documents",
        token=org_a["token"],
        files={"file": ("analyze.txt", b"Org A NDA between Alpha and Beta.", "text/plain")},
        data={"confidentiality": "internal"},
    )
    doc_a = r.json()["id"]

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=org_b["token"],
        json_body={"name": "Org B Matter", "description": "isolated"},
    )
    matter_b = r.json()["id"]

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_b}/analyze",
        token=org_b["token"],
        json_body={"document_id": doc_a, "question": "Who are the parties?"},
        timeout=120.0,
    )
    assert r.status_code in (403, 404)
