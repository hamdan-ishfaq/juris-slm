from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import User
from deps import assert_document_accessible, get_accessible_document_ids
from services.embeddings import embed_texts
from services.llm_client import active_model_name, generate_rag
from services.reranker import rerank
from services.security import check_injection
from services.vector_store import search_similar


def _format_context(hits: list[dict]) -> tuple[str, list[dict]]:
    parts: list[str] = []
    sources: list[dict] = []
    used = 0
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata") or {}
        label = meta.get("title") or meta.get("source") or f"chunk-{h.get('id')}"
        block = f"[{i}] ({label})\n{h['content']}"
        if used + len(block) > settings.rag_max_context_chars:
            break
        parts.append(block)
        used += len(block)
        sources.append({"label": label, "source": meta.get("source"), "distance": h.get("distance")})
    return "\n\n".join(parts), sources


def _guard_query(question: str) -> None:
    lower_q = question.lower()
    suspicious_phrases = [
        "ignore previous instructions",
        "ignore all previous",
        "system prompt",
        "you are now",
        "bypass security",
        "print your instructions",
    ]
    if any(phrase in lower_q for phrase in suspicious_phrases) or len(question) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Query rejected due to potential prompt injection or excessive length.",
        )
    injection = check_injection(question)
    if injection["blocked"]:
        raise HTTPException(
            status_code=400,
            detail="Query rejected due to potential prompt injection (L2 security filter).",
        )


async def answer_question(
    db: AsyncSession,
    question: str,
    *,
    use_law_corpus: bool = True,
    document_id: str | None = None,
    user: User | None = None,
) -> dict:
    _guard_query(question)

    user_role = user.role if user else "member"
    accessible_ids: set[uuid.UUID] | None = None
    doc_uuid: uuid.UUID | None = None

    if user is not None:
        accessible_ids = await get_accessible_document_ids(db, user)

    if document_id:
        doc_uuid = uuid.UUID(document_id)
        if user is not None:
            await assert_document_accessible(db, user, doc_uuid)
        elif accessible_ids is not None and doc_uuid not in accessible_ids:
            raise HTTPException(status_code=403, detail="Document not accessible")

    vectors = embed_texts([question])
    query_vec = vectors[0]

    include_law = use_law_corpus
    search_doc_ids = accessible_ids

    if doc_uuid is not None:
        include_law = False
        search_doc_ids = {doc_uuid}

    hits = await search_similar(
        db,
        query_vec,
        top_k=settings.rag_top_k,
        accessible_document_ids=search_doc_ids,
        include_law_corpus=include_law,
        user_role=user_role,
        document_id=doc_uuid,
    )
    try:
        ranked = rerank(question, hits, top_k=settings.rag_rerank_k)
    except Exception as exc:
        print(f"Rerank skipped ({exc}); using vector order")
        ranked = sorted(hits, key=lambda h: float(h.get("distance", 1.0)))[: settings.rag_rerank_k]
    context, sources = _format_context(ranked)

    if document_id:
        from services.vector_store import fetch_graph_context

        graph_context = await fetch_graph_context(db, question, document_id)
        if graph_context:
            context += "\n" + graph_context

    if not context.strip():
        return {
            "answer": "No relevant context found in the knowledge base. Ingest the law corpus or upload documents first.",
            "model": active_model_name(),
            "sources": [],
        }

    answer = await generate_rag(context, question)
    return {"answer": answer, "model": active_model_name(), "sources": sources}
