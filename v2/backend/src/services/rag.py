from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.embeddings import embed_texts
from services.ollama_client import build_prompt, generate
from services.reranker import rerank
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


async def answer_question(
    db: AsyncSession,
    question: str,
    *,
    use_law_corpus: bool = True,
    document_id: str | None = None,
) -> dict:
    # Query Injection / Jailbreak heuristic checks
    lower_q = question.lower()
    suspicious_phrases = [
        "ignore previous instructions",
        "ignore all previous",
        "system prompt",
        "you are now",
        "bypass security",
        "print your instructions"
    ]
    if any(phrase in lower_q for phrase in suspicious_phrases) or len(question) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Query rejected due to potential prompt injection or excessive length.",
        )

    vectors = embed_texts([question])
    query_vec = vectors[0]
    
    filters = {}
    if use_law_corpus:
        filters["kind"] = "law"
    if document_id:
        filters["document_id"] = document_id
        
    hits = await search_similar(db, query_vec, top_k=settings.rag_top_k, filters=filters if filters else None)
    try:
        ranked = rerank(question, hits, top_k=settings.rag_rerank_k)
    except Exception as exc:
        print(f"Rerank skipped ({exc}); using vector order")
        ranked = sorted(hits, key=lambda h: float(h.get("distance", 1.0)))[: settings.rag_rerank_k]
    context, sources = _format_context(ranked)
    
    # Integrate Graph Context
    if document_id:
        from services.vector_store import fetch_graph_context
        graph_context = await fetch_graph_context(db, question, document_id)
        if graph_context:
            context += "\n" + graph_context
            
    if not context.strip():
        return {
            "answer": "No relevant context found in the knowledge base. Ingest the law corpus or upload documents first.",
            "model": settings.ollama_model,
            "sources": [],
        }
    prompt = build_prompt(context, question)
    answer = await generate(prompt)
    return {"answer": answer, "model": settings.ollama_model, "sources": sources}
