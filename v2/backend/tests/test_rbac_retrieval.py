"""Retrieval-layer RBAC isolation — Phase 1."""
from __future__ import annotations

import asyncio
import time
import uuid

import numpy as np
import pytest

from deps import get_accessible_document_ids
from db import User, async_session_factory
from services.embeddings import embed_texts
from services.vector_store import search_similar
from api_helpers import api_request, register_user


@pytest.mark.integration
def test_cross_user_analyze_blocked(api_up):
    """User B cannot analyze User A's document (handler + access layer)."""
    user_a = register_user()
    user_b = register_user()

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=user_a["token"],
        json_body={"name": "User A Matter", "description": "isolation"},
    )
    matter_a = r.json()["id"]

    nda = b"TechCorp Inc confidential NDA with LegalAI Solutions."
    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_a}/documents",
        token=user_a["token"],
        files={"file": ("user_a_nda.txt", nda, "text/plain")},
        data={"confidentiality": "internal"},
    )
    doc_a = r.json()["id"]

    r = api_request(
        "POST",
        "/api/v1/matters",
        token=user_b["token"],
        json_body={"name": "User B Matter", "description": "isolation"},
    )
    matter_b = r.json()["id"]

    r = api_request(
        "POST",
        f"/api/v1/matters/{matter_b}/analyze",
        token=user_b["token"],
        json_body={"document_id": doc_a, "question": "What parties are named?"},
        timeout=120.0,
    )
    assert r.status_code in (403, 404)


@pytest.mark.integration
def test_search_similar_excludes_other_user_documents(api_up):
    """SQL retrieval filter: User B accessible set must not include User A doc chunks."""

    async def _run() -> None:
        user_a = register_user()
        user_b = register_user()

        r = api_request(
            "POST",
            "/api/v1/matters",
            token=user_a["token"],
            json_body={"name": "Retrieval A", "description": "test"},
        )
        matter_a = r.json()["id"]

        unique = f"UNIQUE_MARKER_{uuid.uuid4().hex[:12]}"
        content = f"{unique} Receiving Party LegalAI Solutions confidentiality obligations."
        r = api_request(
            "POST",
            f"/api/v1/matters/{matter_a}/documents",
            token=user_a["token"],
            files={"file": ("retrieval_test.txt", content.encode(), "text/plain")},
            data={"confidentiality": "internal"},
        )
        doc_a = uuid.UUID(r.json()["id"])

        for _ in range(60):
            st = api_request(
                "GET",
                f"/api/v1/matters/{matter_a}/documents/{doc_a}/status",
                token=user_a["token"],
            )
            if st.json().get("status") == "processed":
                break
            time.sleep(2)
        else:
            pytest.skip("Document not processed in time — worker may be down")

        async with async_session_factory() as db:
            user_b_row = await db.get(User, uuid.UUID(user_b["user_id"]))
            assert user_b_row is not None
            accessible_b = await get_accessible_document_ids(db, user_b_row)
            assert doc_a not in accessible_b

            query_vec = embed_texts([unique])[0]
            hits = await search_similar(
                db,
                query_vec,
                top_k=10,
                accessible_document_ids=accessible_b,
                include_law_corpus=False,
                user_role=user_b_row.role,
            )
            leaked = [h for h in hits if str(h.get("metadata", {}).get("document_id")) == str(doc_a)]
            assert len(leaked) == 0, f"User B retrieval leaked User A chunks: {leaked}"

    asyncio.run(_run())
