from __future__ import annotations

import re
import uuid

import numpy as np
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import User
from deps import assert_document_accessible, get_accessible_document_ids
from services.citation_verifier import verify_citations
from services.embeddings import embed_texts
from services.hyde import generate_hypothetical_document
from services.llm_client import active_model_name, generate_rag
from services.query_decompose import decompose_for_compare, decompose_general
from services.reranker import rerank
from services.rrf import rrf_merge
from services.security import check_injection
from services.vector_store import hybrid_search, search_similar

_REFUSAL_MARKERS = (
    "as an ai",
    "developed by microsoft",
    "i don't have personal",
    "i do not have personal",
    "i cannot assist with",
    "i'm programmed to respect",
    "i am programmed to respect",
)

_STOPWORDS = frozenset(
    {
        "what",
        "when",
        "where",
        "which",
        "that",
        "this",
        "with",
        "from",
        "have",
        "been",
        "will",
        "your",
        "there",
        "their",
        "about",
        "under",
        "article",
    }
)


def _is_model_refusal(answer: str) -> bool:
    lower = answer.lower()
    return any(marker in lower for marker in _REFUSAL_MARKERS)


def _answer_uses_context(answer: str, context: str, *, min_overlap: int = 6) -> bool:
    if _is_model_refusal(answer):
        return False
    ctx_words = {
        w
        for w in re.findall(r"\w{4,}", context.lower())
        if w not in _STOPWORDS
    }
    ans_words = {
        w
        for w in re.findall(r"\w{4,}", answer.lower())
        if w not in _STOPWORDS
    }
    return len(ctx_words & ans_words) >= min_overlap


def _extractive_fallback(context: str, question: str, *, max_chars: int = 800) -> str:
    """Return the most question-relevant context block when the LLM ignores sources."""
    blocks = [b.strip() for b in context.split("\n\n") if b.strip()]
    if not blocks:
        return context[:max_chars]
    q_words = {w.lower() for w in re.findall(r"\w{4,}", question) if w.lower() not in _STOPWORDS}
    best = blocks[0]
    best_score = -1
    for block in blocks:
        lower = block.lower()
        score = sum(1 for w in q_words if w in lower)
        if score > best_score:
            best_score = score
            best = block
    cleaned = re.sub(r"^\[\d+\]\s*\([^)]+\)\s*", "", best).strip()
    return cleaned[:max_chars]


def _boost_section_hits(question: str, hits: list[dict]) -> list[dict]:
    """Promote chunks whose text contains the BGB/GDPR section number asked in the query."""
    match = re.search(r"(?:section|§|sec\.)\s*(\d+)", question, re.IGNORECASE)
    if not match:
        return hits
    num = match.group(1)
    markers = (f"section {num}", f"§ {num}", f"sec. {num}")
    preferred: list[dict] = []
    other: list[dict] = []
    for hit in hits:
        lower = (hit.get("content") or "").lower()
        if any(marker in lower for marker in markers):
            preferred.append(hit)
        else:
            other.append(hit)
    return preferred + other if preferred else hits


def _answer_lacks_article_cite(answer: str) -> bool:
    return re.search(r"(?:article|art\.?)\s*\d+", answer, re.IGNORECASE) is None


def _answer_matches_top_hit(answer: str, top_content: str, *, min_overlap: int = 3) -> bool:
    top_words = {
        w
        for w in re.findall(r"\w{5,}", top_content.lower())[:40]
        if w not in _STOPWORDS
    }
    ans_words = {
        w
        for w in re.findall(r"\w{4,}", answer.lower())
        if w not in _STOPWORDS
    }
    return len(top_words & ans_words) >= min_overlap


def _format_context(hits: list[dict]) -> tuple[str, list[dict]]:
    parts: list[str] = []
    sources: list[dict] = []
    used = 0
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata") or {}
        label = meta.get("title") or meta.get("source") or f"chunk-{h.get('id')}"
        body = meta.get("parent_content") or h["content"]
        block = f"[{i}] ({label})\n{body}"
        if used + len(block) > settings.rag_max_context_chars:
            break
        parts.append(block)
        sources.append(
            {
                "label": label,
                "source": meta.get("source"),
                "distance": h.get("distance"),
                "rerank_score": h.get("rerank_score"),
            }
        )
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


def _short_query_refusal(question: str, *, document_id: str | None) -> dict | None:
    """Refuse ultra-short general queries that cannot be answered reliably."""
    if document_id:
        return None
    words = [w for w in question.strip().split() if w]
    if len(words) >= settings.rag_min_query_words:
        return None
    return {
        "answer": (
            "Your question is too short to answer reliably. "
            "Please ask a specific legal question (e.g. about a GDPR article or contract clause)."
        ),
        "model": active_model_name(),
        "sources": [],
    }


_ART6_BASIS_PHRASES: dict[str, str] = {
    "a": "consent",
    "b": "performance of a contract",
    "c": "compliance with a legal obligation",
    "d": "protect the vital interests",
    "e": "public interest",
    "f": "legitimate interests",
}


def _query_has_explicit_article_paragraph(question: str) -> bool:
    return bool(re.search(r"(?:article|art\.?)\s*\d+\s*\(\s*\d+\s*\)", question, re.IGNORECASE))


def _boost_art6_basis_hits(question: str, hits: list[dict]) -> list[dict]:
    """Promote chunks matching an explicit Art 6(1)(x) letter when the query names it."""
    match = re.search(
        r"(?:article|art\.?)\s*6\s*\(\s*1\s*\)\s*\(\s*([a-f])\s*\)",
        question,
        re.IGNORECASE,
    )
    if not match:
        return hits
    phrase = _ART6_BASIS_PHRASES.get(match.group(1).lower())
    if not phrase:
        return hits
    preferred: list[dict] = []
    other: list[dict] = []
    for hit in hits:
        if phrase in (hit.get("content") or "").lower():
            preferred.append(hit)
        else:
            other.append(hit)
    return preferred + other if preferred else hits


def _average_vectors(vectors: list[np.ndarray]) -> np.ndarray:
    if len(vectors) == 1:
        return vectors[0]
    stacked = np.stack(vectors, axis=0)
    mean = stacked.mean(axis=0)
    norm = np.linalg.norm(mean)
    if norm > 0:
        mean = mean / norm
    return mean.astype(np.float32)


async def _embed_query(question: str, *, use_hyde: bool) -> tuple[np.ndarray, str]:
    """Embed question; optionally blend with HyDE hypothetical document vector."""
    hyde_on = (use_hyde or settings.hyde_enabled) and not _query_has_explicit_article_paragraph(
        question
    )
    if not hyde_on:
        return embed_texts([question])[0], question

    hypo = await generate_hypothetical_document(question)
    vectors = embed_texts([question, hypo])
    return _average_vectors(vectors), hypo


async def _retrieve(
    db: AsyncSession,
    question: str,
    query_vec: np.ndarray,
    *,
    accessible_ids: set[uuid.UUID] | None,
    include_law: bool,
    user_role: str,
    doc_uuid: uuid.UUID | None,
) -> list[dict]:
    if settings.hybrid_search_enabled:
        return await hybrid_search(
            db,
            question,
            query_vec,
            top_k=settings.rag_top_k,
            accessible_document_ids=accessible_ids,
            include_law_corpus=include_law,
            user_role=user_role,
            document_id=doc_uuid,
        )
    return await search_similar(
        db,
        query_vec,
        top_k=settings.rag_top_k,
        accessible_document_ids=accessible_ids,
        include_law_corpus=include_law,
        user_role=user_role,
        document_id=doc_uuid,
    )


async def _retrieve_multi_query(
    db: AsyncSession,
    sub_questions: list[str],
    *,
    accessible_ids: set[uuid.UUID] | None,
    include_law: bool,
    user_role: str,
    doc_uuid: uuid.UUID | None,
    use_hyde: bool = False,
) -> list[dict]:
    """Multi-query retrieval with RRF merge (Phase 2.8)."""
    lists: list[list[dict]] = []
    for sub_q in sub_questions:
        q_vec, _ = await _embed_query(sub_q, use_hyde=use_hyde)
        hits = await _retrieve(
            db,
            sub_q,
            q_vec,
            accessible_ids=accessible_ids,
            include_law=include_law,
            user_role=user_role,
            doc_uuid=doc_uuid,
        )
        if hits:
            lists.append(hits)
    if not lists:
        return []
    if len(lists) == 1:
        return lists[0]
    return rrf_merge(lists, k=settings.rag_rrf_k, top_k=settings.rag_top_k)


def _apply_confidence_gate(ranked: list[dict]) -> bool:
    """Return True if retrieval confidence is sufficient (Phase 2.5)."""
    if not ranked:
        return False
    if "rerank_score" in ranked[0]:
        return float(ranked[0]["rerank_score"]) >= settings.rag_min_rerank_score
    return True


async def answer_question(
    db: AsyncSession,
    question: str,
    *,
    use_law_corpus: bool = True,
    document_id: str | None = None,
    user: User | None = None,
    use_hyde: bool = False,
    multi_query: bool = False,
) -> dict:
    _guard_query(question)
    if short := _short_query_refusal(question, document_id=document_id):
        return short

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

    include_law = use_law_corpus
    search_doc_ids = accessible_ids

    if doc_uuid is not None:
        include_law = False
        search_doc_ids = {doc_uuid}
    elif use_law_corpus:
        # Statute Q&A must not pull unrelated contract chunks from the user's matters.
        search_doc_ids = None

    if multi_query:
        subs = decompose_general(question)
        hits = await _retrieve_multi_query(
            db,
            subs,
            accessible_ids=search_doc_ids,
            include_law=include_law,
            user_role=user_role,
            doc_uuid=doc_uuid,
            use_hyde=use_hyde,
        )
    else:
        query_vec, _ = await _embed_query(question, use_hyde=use_hyde)
        hits = await _retrieve(
            db,
            question,
            query_vec,
            accessible_ids=search_doc_ids,
            include_law=include_law,
            user_role=user_role,
            doc_uuid=doc_uuid,
        )

    hits = _boost_art6_basis_hits(question, hits)
    hits = _boost_section_hits(question, hits)

    try:
        ranked = rerank(question, hits, top_k=settings.rag_rerank_k)
    except Exception as exc:
        print(f"Rerank skipped ({exc}); using retrieval order")
        ranked = hits[: settings.rag_rerank_k]

    if not _apply_confidence_gate(ranked):
        return {
            "answer": (
                "Insufficient relevant context was found to answer this question reliably. "
                "Try rephrasing, enabling law corpus search, or uploading additional documents."
            ),
            "model": active_model_name(),
            "sources": [],
        }

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
    needs_article = bool(re.search(r"\bgdpr\b|article\s+\d", question, re.IGNORECASE))
    top_content = (ranked[0].get("content") or "") if ranked else ""
    if (
        _is_model_refusal(answer)
        or not _answer_uses_context(answer, context)
        or (needs_article and _answer_lacks_article_cite(answer))
        or (top_content and not _answer_matches_top_hit(answer, top_content))
    ):
        answer = _extractive_fallback(context, question)

    if settings.citation_verify_enabled:
        hit_contents = [h.get("content", "") for h in ranked]
        answer, _ = verify_citations(answer, sources, hit_contents)

    return {"answer": answer, "model": active_model_name(), "sources": sources}


async def answer_compare(
    db: AsyncSession,
    question: str,
    *,
    document_id: str,
    user: User,
) -> dict:
    """Compare flow: multi-query decomposition over document + law corpus."""
    _guard_query(question)
    subs = decompose_for_compare(question)

    doc_result = await answer_question(
        db,
        question,
        use_law_corpus=False,
        document_id=document_id,
        user=user,
        multi_query=True,
    )
    law_result = await answer_question(
        db,
        subs[0] if subs else question,
        use_law_corpus=True,
        user=user,
        use_hyde=False,
        multi_query=len(subs) > 1,
    )
    combined = (
        f"## Document analysis\n{doc_result['answer']}\n\n"
        f"## Regulatory baseline (GDPR/BGB)\n{law_result['answer']}"
    )
    return {
        "answer": combined,
        "model": active_model_name(),
        "sources": doc_result.get("sources", []) + law_result.get("sources", []),
        "comparison_result": combined,
    }
