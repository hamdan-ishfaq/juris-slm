from __future__ import annotations

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
) -> dict:
    vectors = embed_texts([question])
    query_vec = vectors[0]
    hits = await search_similar(db, query_vec, top_k=settings.rag_top_k)
    if use_law_corpus:
        law_hits = [h for h in hits if (h.get("metadata") or {}).get("kind") == "law"]
        if law_hits:
            hits = law_hits
    try:
        ranked = rerank(question, hits, top_k=settings.rag_rerank_k)
    except Exception as exc:
        print(f"Rerank skipped ({exc}); using vector order")
        ranked = sorted(hits, key=lambda h: float(h.get("distance", 1.0)))[: settings.rag_rerank_k]
    context, sources = _format_context(ranked)
    if not context.strip():
        return {
            "answer": "No relevant context found in the knowledge base. Ingest the law corpus or upload documents first.",
            "model": settings.ollama_model,
            "sources": [],
        }
    prompt = build_prompt(context, question)
    answer = await generate(prompt)
    return {"answer": answer, "model": settings.ollama_model, "sources": sources}
