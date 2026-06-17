from __future__ import annotations

import json
import re
import uuid
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.access_control import can_access_confidentiality
from services.rrf import rrf_merge


def _vector_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in vec.tolist()) + "]"


def _sanitize_fts_query(query_text: str) -> str:
    """Prepare query for plainto_tsquery — strip special chars, keep legal tokens."""
    cleaned = re.sub(r"[^\w\s\-§./()]", " ", query_text)
    return " ".join(cleaned.split())[:500]


def _build_access_sql(
    *,
    accessible_document_ids: set[uuid.UUID] | None,
    include_law_corpus: bool,
    user_role: str,
    document_id: uuid.UUID | None,
    filters: dict[str, Any] | None,
    params: dict[str, Any],
) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    access_parts: list[str] = []

    if include_law_corpus:
        access_parts.append("metadata->>'kind' = 'law'")

    if accessible_document_ids:
        params["doc_ids"] = [str(d) for d in accessible_document_ids]
        access_parts.append("document_id = ANY(CAST(:doc_ids AS uuid[]))")

    if not access_parts:
        return [], params

    conditions.append("(" + " OR ".join(access_parts) + ")")

    if document_id is not None:
        params["single_doc_id"] = str(document_id)
        conditions.append("document_id = CAST(:single_doc_id AS uuid)")

    conditions.append(
        """(
            metadata->>'kind' = 'law'
            OR COALESCE(metadata->>'confidentiality', 'internal') = 'internal'
            OR (:user_role IN ('matter_lead', 'org_admin', 'owner')
                AND COALESCE(metadata->>'confidentiality', 'internal') = 'restricted')
            OR (:user_role IN ('org_admin', 'owner')
                AND COALESCE(metadata->>'confidentiality', 'internal') = 'privileged')
        )"""
    )

    if filters:
        for key, value in filters.items():
            if key in ("document_id", "kind"):
                continue
            param_key = f"filter_{key}"
            conditions.append(f"metadata->>'{key}' = :{param_key}")
            params[param_key] = str(value)

    return conditions, params


def _post_filter_hits(rows, user_role: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        meta = meta or {}
        conf = meta.get("confidentiality", "internal")
        kind = meta.get("kind")
        if kind != "law" and not can_access_confidentiality(user_role, conf):
            continue
        out.append(
            {
                "id": row["id"],
                "content": row["content"],
                "metadata": meta,
                "distance": float(row.get("distance", 1.0)),
            }
        )
    return out


async def insert_chunk(
    db: AsyncSession,
    *,
    document_id: uuid.UUID,
    chunk_index: int,
    content: str,
    embedding: np.ndarray,
    metadata: dict[str, Any],
) -> None:
    await db.execute(
        text(
            """
            INSERT INTO document_chunks (document_id, chunk_index, content, embedding, metadata)
            VALUES (:document_id, :chunk_index, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
            """
        ),
        {
            "document_id": str(document_id),
            "chunk_index": chunk_index,
            "content": content,
            "embedding": _vector_literal(embedding),
            "metadata": json.dumps(metadata),
        },
    )


async def delete_by_document_id(db: AsyncSession, document_id: uuid.UUID) -> int:
    result = await db.execute(
        text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
        {"doc_id": str(document_id)},
    )
    return result.rowcount or 0


async def search_similar(
    db: AsyncSession,
    query_embedding: np.ndarray,
    *,
    top_k: int | None = None,
    accessible_document_ids: set[uuid.UUID] | None = None,
    include_law_corpus: bool = False,
    user_role: str = "member",
    document_id: uuid.UUID | None = None,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Vector-only search with retrieval-layer RBAC (Phase 1)."""
    k = top_k or settings.rag_top_k
    params: dict[str, Any] = {
        "q": _vector_literal(query_embedding),
        "k": k,
        "user_role": user_role,
    }

    conditions, params = _build_access_sql(
        accessible_document_ids=accessible_document_ids,
        include_law_corpus=include_law_corpus,
        user_role=user_role,
        document_id=document_id,
        filters=filters,
        params=params,
    )
    if not conditions:
        return []

    sql = """
        SELECT id, content, metadata,
               (embedding <=> CAST(:q AS vector)) AS distance
        FROM document_chunks
        WHERE """ + " AND ".join(conditions) + """
        ORDER BY distance ASC
        LIMIT :k
    """
    rows = await db.execute(text(sql), params)
    return _post_filter_hits(rows.mappings(), user_role)


async def search_fts(
    db: AsyncSession,
    query_text: str,
    *,
    top_k: int | None = None,
    accessible_document_ids: set[uuid.UUID] | None = None,
    include_law_corpus: bool = False,
    user_role: str = "member",
    document_id: uuid.UUID | None = None,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Full-text (BM25-style) branch for hybrid search."""
    k = top_k or settings.rag_top_k
    fts_q = _sanitize_fts_query(query_text)
    if not fts_q:
        return []

    params: dict[str, Any] = {
        "fts_q": fts_q,
        "k": k,
        "user_role": user_role,
    }
    conditions, params = _build_access_sql(
        accessible_document_ids=accessible_document_ids,
        include_law_corpus=include_law_corpus,
        user_role=user_role,
        document_id=document_id,
        filters=filters,
        params=params,
    )
    if not conditions:
        return []

    conditions.append("content_tsv @@ plainto_tsquery('simple', :fts_q)")

    sql = """
        SELECT id, content, metadata,
               ts_rank(content_tsv, plainto_tsquery('simple', :fts_q)) AS distance
        FROM document_chunks
        WHERE """ + " AND ".join(conditions) + """
        ORDER BY distance DESC
        LIMIT :k
    """
    try:
        rows = await db.execute(text(sql), params)
    except Exception:
        return []
    hits = _post_filter_hits(rows.mappings(), user_role)
    for h in hits:
        h["distance"] = 1.0 - min(float(h.get("distance", 0)), 1.0)
    return hits


async def hybrid_search(
    db: AsyncSession,
    query_text: str,
    query_embedding: np.ndarray,
    *,
    top_k: int | None = None,
    accessible_document_ids: set[uuid.UUID] | None = None,
    include_law_corpus: bool = False,
    user_role: str = "member",
    document_id: uuid.UUID | None = None,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Hybrid retrieval: vector + FTS merged with Reciprocal Rank Fusion (Phase 2.1).
    Falls back to vector-only if FTS column missing or returns empty.
    """
    k = top_k or settings.rag_top_k
    branch_k = max(k * 2, 20)

    vec_hits = await search_similar(
        db,
        query_embedding,
        top_k=branch_k,
        accessible_document_ids=accessible_document_ids,
        include_law_corpus=include_law_corpus,
        user_role=user_role,
        document_id=document_id,
        filters=filters,
    )

    if not settings.hybrid_search_enabled:
        return vec_hits[:k]

    fts_hits = await search_fts(
        db,
        query_text,
        top_k=branch_k,
        accessible_document_ids=accessible_document_ids,
        include_law_corpus=include_law_corpus,
        user_role=user_role,
        document_id=document_id,
        filters=filters,
    )

    if not fts_hits:
        return vec_hits[:k]

    merged = rrf_merge([vec_hits, fts_hits], k=settings.rag_rrf_k, top_k=k)
    return merged if merged else vec_hits[:k]


async def corpus_stats(db: AsyncSession) -> dict[str, Any]:
    total = await db.execute(text("SELECT COUNT(*) AS c FROM document_chunks"))
    count = int(total.scalar_one())
    by_source_rows = await db.execute(
        text(
            """
            SELECT COALESCE(metadata->>'source', 'unknown') AS source, COUNT(*) AS c
            FROM document_chunks
            GROUP BY 1
            ORDER BY 2 DESC
            """
        )
    )
    by_source = {r["source"]: int(r["c"]) for r in by_source_rows.mappings()}
    return {"total_chunks": count, "by_source": by_source}


async def fetch_graph_context(db: AsyncSession, query: str, document_id: str) -> str:
    words = [w.lower() for w in query.split() if len(w) > 3]
    if not words:
        return ""

    conditions = " OR ".join([f"LOWER(n.name) LIKE :w{i}" for i in range(len(words))])
    params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
    params["doc_id"] = document_id

    sql = f"""
        SELECT DISTINCT dc.content
        FROM graph_nodes n
        JOIN graph_edges e ON (n.id = e.source_node_id OR n.id = e.target_node_id)
        JOIN document_chunks dc ON (dc.document_id = n.document_id AND dc.chunk_index = e.chunk_index)
        WHERE n.document_id = CAST(:doc_id AS UUID) AND ({conditions})
        LIMIT 3
    """
    rows = await db.execute(text(sql), params)
    graph_chunks = [row[0] for row in rows]
    if graph_chunks:
        return "\n\n[GRAPH CONTEXT]\n" + "\n\n".join(graph_chunks)
    return ""
