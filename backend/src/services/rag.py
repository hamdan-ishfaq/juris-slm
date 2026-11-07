from __future__ import annotations

import asyncio
import json
import re
import time
import uuid

import numpy as np
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import User
from deps import assert_document_accessible, get_accessible_document_ids
from services.citation_verifier import verify_citations
from services.embeddings import embed_texts
from services.hyde import generate_hypothetical_document
from services.llm_client import active_model_name, generate_rag
from services.metrics import FIRST_TOKEN_SECONDS
from services.query_cache import get_cached_answer, set_cached_answer
from services.tracing import collect_stage_times, trace_rag_step
from services.document_routing import focus_question, route_to_document
from services.query_decompose import decompose_for_compare, decompose_general
from services.query_enhance import adaptive_use_hyde, crag_rewrite_query
from services.reranker import rerank, score_hits
from services.rrf import rrf_merge
from services.security import check_injection_full as check_injection
from services.vector_store import cited_provisions, has_legal_reference, hybrid_search, search_similar

_REFUSAL_MARKERS = (
    "as an ai",
    "developed by microsoft",
    "i don't have personal",
    "i do not have personal",
    "i cannot assist with",
    "i'm programmed to respect",
    "i am programmed to respect",
)

ANSWER_LLM = "llm"
ANSWER_EXTRACTIVE = "extractive"
ANSWER_REFUSED = "refused"

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


def _answer_uses_context(
    answer: str,
    context: str,
    *,
    chunk_vectors: list[np.ndarray] | None = None,
    min_overlap: int = 6,
) -> bool:
    """True when the answer is close to a retrieved chunk (bge-m3 cosine) or shares enough words with the context.

    The chunks' stored vectors are reused, so only the answer is embedded: embedding the chunks again took about 3.5 s
    on the CPU for every question.
    """
    if _is_model_refusal(answer):
        return False
    if not answer.strip():
        return False

    if chunk_vectors:
        answer_vector = embed_texts([answer[:1500]])[0]
        sims = [
            float(np.dot(answer_vector, vector) / (np.linalg.norm(answer_vector) * np.linalg.norm(vector)))
            for vector in chunk_vectors
        ]
        if max(sims) >= settings.semantic_context_min_cosine:
            return True

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


def _dedupe_hits(hits: list[dict], *, prefix_len: int = 200) -> list[dict]:
    """Remove near-duplicate chunks to save rerank/context budget."""
    seen: set[str] = set()
    out: list[dict] = []
    for h in hits:
        body = (h.get("content") or "")[:prefix_len].strip().lower()
        if not body or body in seen:
            continue
        seen.add(body)
        out.append(h)
    return out


_CONTEXT_SEPARATOR = "\n\n"
# Results from a document the question names outrank global ones, which remain in case the guess was wrong.
_NAMED_DOCUMENT_WEIGHT = 4.0


def _format_context(hits: list[dict]) -> tuple[str, list[dict]]:
    parts: list[str] = []
    sources: list[dict] = []
    used = 0
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata") or {}
        label = meta.get("title") or meta.get("source") or f"chunk-{h.get('id')}"
        header = f"[{i}] ({label})\n"
        room = settings.rag_max_context_chars - used - len(header)
        # A section too long to fit would crowd out the clause that matched, so send that clause alone.
        body = meta.get("parent_content") or h["content"]
        if len(body) > room:
            body = h["content"]
        if len(body) > room:
            if parts:
                break
            body = body[:room]
        block = header + body
        parts.append(block)
        used += len(block) + len(_CONTEXT_SEPARATOR)
        snippet = body[:2000]
        sources.append(
            {
                "chunk_id": str(h.get("id") or meta.get("chunk_id") or ""),
                "label": label,
                "source": meta.get("source"),
                "content": snippet,
                "char_start": 0,
                "char_end": len(snippet),
                "distance": h.get("distance"),
                "rerank_score": h.get("rerank_score"),
            }
        )
    return _CONTEXT_SEPARATOR.join(parts), sources


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
        "answer_mode": ANSWER_REFUSED,
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
    org_id: uuid.UUID | None = None,
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
            org_id=org_id,
        )
    return await search_similar(
        db,
        query_vec,
        top_k=settings.rag_top_k,
        accessible_document_ids=accessible_ids,
        include_law_corpus=include_law,
        user_role=user_role,
        document_id=doc_uuid,
        org_id=org_id,
    )


async def _stored_vectors(db: AsyncSession, chunk_ids: list[int]) -> list[np.ndarray]:
    rows = await db.execute(
        text("SELECT embedding::text AS vector FROM document_chunks WHERE id = ANY(:ids)"),
        {"ids": chunk_ids},
    )
    return [np.array(json.loads(row["vector"]), dtype=np.float32) for row in rows.mappings()]


async def _document_titles(db: AsyncSession, document_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    rows = await db.execute(
        text(
            """
            SELECT DISTINCT ON (document_id) document_id, metadata->>'title' AS title
            FROM document_chunks
            WHERE document_id = ANY(CAST(:ids AS uuid[])) AND metadata->>'title' IS NOT NULL
            ORDER BY document_id
            """
        ),
        {"ids": [str(document_id) for document_id in document_ids]},
    )
    return {row["document_id"]: row["title"] for row in rows.mappings()}


async def _retrieve_and_rank(
    db: AsyncSession,
    question: str,
    *,
    accessible_ids: set[uuid.UUID] | None,
    include_law: bool,
    user_role: str,
    doc_uuid: uuid.UUID | None,
    use_hyde: bool,
    multi_query: bool = False,
    org_id: uuid.UUID | None = None,
) -> list[dict]:
    """Retrieve, dedupe, rerank; CRAG-lite retry on weak confidence."""
    hyde_on = adaptive_use_hyde(question, use_hyde=use_hyde)

    async def _pass(q: str, *, hyde: bool) -> list[dict]:
        if multi_query:
            subs = decompose_general(q)
            hits = await _retrieve_multi_query(
                db,
                subs,
                accessible_ids=accessible_ids,
                include_law=include_law,
                user_role=user_role,
                doc_uuid=doc_uuid,
                use_hyde=hyde,
                org_id=org_id,
            )
        else:
            with trace_rag_step("embed"):
                query_vec, _ = await _embed_query(q, use_hyde=hyde)
            with trace_rag_step("search"):
                hits = await _retrieve(
                    db,
                    q,
                    query_vec,
                    accessible_ids=accessible_ids,
                    include_law=include_law,
                    user_role=user_role,
                    doc_uuid=doc_uuid,
                    org_id=org_id,
                )
            if not include_law and doc_uuid is None and accessible_ids:
                titles = await _document_titles(db, accessible_ids)
                named = route_to_document(q, titles)
                if named is not None:
                    focused = focus_question(q, titles[named])
                    focused_vec, _ = await _embed_query(focused, use_hyde=False)
                    scoped = await _retrieve(
                        db,
                        focused,
                        focused_vec,
                        accessible_ids={named},
                        include_law=False,
                        user_role=user_role,
                        doc_uuid=None,
                        org_id=org_id,
                    )
                    hits = rrf_merge(
                        [scoped, hits],
                        k=settings.rag_rrf_k,
                        top_k=settings.rag_top_k,
                        weights=[_NAMED_DOCUMENT_WEIGHT, 1.0],
                    )
        hits = _dedupe_hits(hits)
        try:
            with trace_rag_step("rerank"):
                # Reordering helped on English statutes, and hurt on contracts and German. Every
                # question still needs scores for the confidence gate. See docs/DECISIONS.md, D-004, D-006.
                if (include_law or has_legal_reference(q)) and not looks_german(q):
                    ranked = rerank(q, hits, top_k=settings.rag_rerank_k)
                else:
                    ranked = score_hits(q, hits[: settings.rag_rerank_k])
        except Exception as exc:
            print(f"Rerank skipped ({exc}); using retrieval order")
            ranked = hits[: settings.rag_rerank_k]
        return ranked

    ranked = await _pass(question, hyde=hyde_on)
    if _apply_confidence_gate(ranked, question):
        return ranked

    if settings.crag_retry_enabled:
        rewrite = crag_rewrite_query(question)
        if rewrite != question:
            retry_hyde = hyde_on and not settings.is_airgap_latency_profile
            retry = await _pass(rewrite, hyde=retry_hyde)
            if _apply_confidence_gate(retry, question):
                return retry
    return ranked


async def _retrieve_multi_query(
    db: AsyncSession,
    sub_questions: list[str],
    *,
    accessible_ids: set[uuid.UUID] | None,
    include_law: bool,
    user_role: str,
    doc_uuid: uuid.UUID | None,
    use_hyde: bool = False,
    org_id: uuid.UUID | None = None,
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
            org_id=org_id,
        )
        if hits:
            lists.append(hits)
    if not lists:
        return []
    if len(lists) == 1:
        return lists[0]
    return rrf_merge(lists, k=settings.rag_rrf_k, top_k=settings.rag_top_k)


_GERMAN_WORDS = frozenset(
    """der das den dem und oder ein eine einer eines ist sind wird werden nach von mit für auf über wann wie welche welchen
    welcher welches darf muss kann nicht auch zu im regelt gilt daten""".split()
)
_MIN_GERMAN_WORD_SHARE = 0.12
_MAX_WORDS_FOR_UMLAUT_ALONE = 3


def looks_german(text_value: str) -> bool:
    words = re.findall(r"\w+", text_value.lower())
    if not words:
        return False
    if len(words) <= _MAX_WORDS_FOR_UMLAUT_ALONE and re.search(r"[äöüß]", text_value.lower()):
        return True
    return sum(word in _GERMAN_WORDS for word in words) / len(words) >= _MIN_GERMAN_WORD_SHARE


def _apply_confidence_gate(ranked: list[dict], question: str = "") -> bool:
    """Return True if retrieval confidence is sufficient. See docs/DECISIONS.md, D-006."""
    if not ranked:
        return False
    if "rerank_score" not in ranked[0]:
        return True
    if looks_german(question) or any(looks_german(hit.get("content", "")) for hit in ranked):
        return True
    retrieved = {str((hit.get("metadata") or {}).get("article")) for hit in ranked}
    if cited_provisions(question) & retrieved:
        return True
    return max(float(hit["rerank_score"]) for hit in ranked) >= settings.rag_min_rerank_score


async def load_thread_history(
    db: AsyncSession,
    thread_id: uuid.UUID,
    *,
    max_turns: int = 6,
) -> list[dict[str, str]]:
    from sqlalchemy import select

    from db import ChatMessage

    rows = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(max_turns * 2)
    )
    msgs = list(reversed(rows.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]


def _history_block(history: list[dict[str, str]] | None) -> str:
    if not history:
        return ""
    lines = []
    for m in history[-12:]:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content'][:800]}")
    return "Prior conversation:\n" + "\n".join(lines) + "\n\n"


async def answer_question(
    db: AsyncSession,
    question: str,
    *,
    use_law_corpus: bool = True,
    document_id: str | None = None,
    user: User | None = None,
    use_hyde: bool = False,
    multi_query: bool = False,
    history: list[dict[str, str]] | None = None,
    skip_cache: bool = False,
) -> dict:
    """Answer a question, reporting the milliseconds each stage took in ``timings_ms``."""
    with collect_stage_times() as times:
        with trace_rag_step("total", **{"question.chars": len(question)}) as span:
            result = await _answer_question(
                db,
                question,
                use_law_corpus=use_law_corpus,
                document_id=document_id,
                user=user,
                use_hyde=use_hyde,
                multi_query=multi_query,
                history=history,
                skip_cache=skip_cache,
            )
            span.set_attribute("answer.mode", result.get("answer_mode", ""))
            span.set_attribute("answer.cached", bool(result.get("cached")))
            span.set_attribute("sources.count", len(result.get("sources") or []))
    return {**result, "timings_ms": {stage: round(ms, 1) for stage, ms in times.items()}}


async def _answer_question(
    db: AsyncSession,
    question: str,
    *,
    use_law_corpus: bool = True,
    document_id: str | None = None,
    user: User | None = None,
    use_hyde: bool = False,
    multi_query: bool = False,
    history: list[dict[str, str]] | None = None,
    skip_cache: bool = False,
) -> dict:
    with trace_rag_step("guard"):
        _guard_query(question)
    if short := _short_query_refusal(question, document_id=document_id):
        return short

    cached = (
        None
        if skip_cache
        else get_cached_answer(question, use_law_corpus=use_law_corpus, document_id=document_id)
    )
    if cached:
        return {**cached, "cached": True}

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

    with trace_rag_step("retrieve"):
        ranked = await _retrieve_and_rank(
            db,
            question,
            accessible_ids=search_doc_ids,
            include_law=include_law,
            user_role=user_role,
            doc_uuid=doc_uuid,
            use_hyde=use_hyde,
            multi_query=multi_query,
            org_id=user.org_id if user else None,
        )

    if not _apply_confidence_gate(ranked, question):
        return {
            "answer": (
                "Insufficient relevant context was found to answer this question reliably. "
                "Try rephrasing, enabling law corpus search, or uploading additional documents."
            ),
            "model": active_model_name(),
            "sources": [],
            "answer_mode": ANSWER_REFUSED,
        }

    context, sources = _format_context(ranked)

    if document_id:
        from services.vector_store import fetch_graph_context

        graph_context = await fetch_graph_context(db, question, document_id)
        if graph_context:
            context += "\n" + graph_context
    elif use_law_corpus and not document_id:
        from services.dlg import fetch_dlg_context

        dlg = await fetch_dlg_context(db, question)
        if dlg:
            context += "\n" + dlg

    if not context.strip():
        return {
            "answer": "No relevant context found in the knowledge base. Ingest the law corpus or upload documents first.",
            "model": active_model_name(),
            "sources": [],
            "answer_mode": ANSWER_REFUSED,
        }

    hist = _history_block(history)
    with trace_rag_step("generate"):
        answer = await generate_rag(hist + context, question)
    answer_mode = ANSWER_LLM
    needs_article = bool(re.search(r"\bgdpr\b|article\s+\d", question, re.IGNORECASE))
    top_content = (ranked[0].get("content") or "") if ranked else ""
    refused = _is_model_refusal(answer)
    grounded = False
    if not refused:
        with trace_rag_step("grounding"):
            chunk_ids = [hit["id"] for hit in ranked[:5] if hit.get("id") is not None]
            chunk_vectors = await _stored_vectors(db, chunk_ids) if chunk_ids else []
            grounded = await asyncio.to_thread(_answer_uses_context, answer, context, chunk_vectors=chunk_vectors)
    if (
        refused
        or not grounded
        or (needs_article and _answer_lacks_article_cite(answer))
        or (top_content and not _answer_matches_top_hit(answer, top_content))
    ):
        answer = _extractive_fallback(context, question)
        answer_mode = ANSWER_EXTRACTIVE

    if settings.citation_verify_enabled:
        hit_contents = [h.get("content", "") for h in ranked]
        with trace_rag_step("verify"):
            answer, _ = verify_citations(answer, sources, hit_contents)

    result = {
        "answer": answer,
        "model": active_model_name(),
        "sources": sources,
        "cached": False,
        "answer_mode": answer_mode,
    }
    set_cached_answer(
        question,
        use_law_corpus=use_law_corpus,
        document_id=document_id,
        payload=result,
    )
    return result


async def answer_question_stream(
    db: AsyncSession,
    question: str,
    *,
    use_law_corpus: bool = True,
    document_id: str | None = None,
    user: User | None = None,
    use_hyde: bool = False,
    history: list[dict[str, str]] | None = None,
):
    """Yield SSE-style dict events: token, sources, meta."""
    started = time.perf_counter()
    from services.llm_client import generate_rag_stream

    _guard_query(question)
    if short := _short_query_refusal(question, document_id=document_id):
        yield {"type": "token", "content": short["answer"]}
        yield {"type": "sources", "sources": short.get("sources") or []}
        yield {"type": "meta", "model": short.get("model")}
        return

    user_role = user.role if user else "member"
    accessible_ids: set[uuid.UUID] | None = None
    doc_uuid: uuid.UUID | None = None
    if user is not None:
        accessible_ids = await get_accessible_document_ids(db, user)
    if document_id:
        doc_uuid = uuid.UUID(document_id)
        if user is not None:
            await assert_document_accessible(db, user, doc_uuid)

    include_law = use_law_corpus
    search_doc_ids = accessible_ids
    if doc_uuid is not None:
        include_law = False
        search_doc_ids = {doc_uuid}
    elif use_law_corpus:
        search_doc_ids = None

    ranked = await _retrieve_and_rank(
        db,
        question,
        accessible_ids=search_doc_ids,
        include_law=include_law,
        user_role=user_role,
        doc_uuid=doc_uuid,
        use_hyde=use_hyde,
        org_id=user.org_id if user else None,
    )

    if not _apply_confidence_gate(ranked, question):
        msg = (
            "Insufficient relevant context was found to answer this question reliably. "
            "Try rephrasing, enabling law corpus search, or uploading additional documents."
        )
        yield {"type": "token", "content": msg}
        yield {"type": "sources", "sources": []}
        yield {"type": "meta", "model": active_model_name()}
        return

    context, sources = _format_context(ranked)
    if use_law_corpus and not document_id:
        from services.dlg import fetch_dlg_context

        dlg = await fetch_dlg_context(db, question)
        if dlg:
            context += "\n" + dlg

    hist = _history_block(history)
    model = active_model_name()
    yield {"type": "meta", "model": model}
    full = ""
    first_token_at: float | None = None
    async for chunk in generate_rag_stream(hist + context, question):
        full += chunk
        yield {"type": "token", "content": chunk}
        if first_token_at is None:
            first_token_at = time.perf_counter()
            FIRST_TOKEN_SECONDS.observe(first_token_at - started)
    yield {"type": "sources", "sources": sources}


async def answer_compare(
    db: AsyncSession,
    question: str,
    *,
    document_id: str,
    user: User,
) -> dict:
    """Compare flow: document + law RAG, one after the other because they share a session."""
    _guard_query(question)
    subs = decompose_for_compare(question)
    law_q = subs[0] if subs else question

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
        law_q,
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
